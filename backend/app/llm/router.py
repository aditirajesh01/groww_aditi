"""The cascade: gemini -> openrouter -> template.

Everything that makes free tiers survivable lives here, in front of the
providers rather than inside them:

*   **Token bucket** per provider (RPM). Refuses locally instead of spending a
    request to be told 429.
*   **Daily quota tracker** per provider, persisted per UTC day. The configured
    cap is a cold start; when a provider reports its real quota in a 429 we
    persist that and use it from then on. Free-tier limits change without
    notice, so the live number is the authoritative one.
*   **Circuit breaker** per provider. Consecutive failures open the circuit for
    a cooldown so a dead provider costs one request per cooldown rather than
    one per item.
*   **Exponential backoff with jitter** on retryable errors, bounded, and never
    on the read path.

The cascade *always terminates at the template*, which needs no key, no network
and no quota. That is why "no API keys at all" is a supported configuration
rather than a degraded one: the last stop cannot fail.

Every bit of this state is surfaced on `GET /health` (see the health fixture),
because degradation the operator cannot see is indistinguishable from a bug.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import iso, utc_now
from ..config import settings
from ..schemas import ProviderHealth
from . import cache as llm_cache
from . import compliance
from .base import (
    Completion,
    ProviderError,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    SummaryRequest,
    ThesisRequest,
)
from .gemini import GeminiProvider
from .openrouter import OpenRouterProvider
from .prompts import evidence_blob
from .template import TemplateProvider

log = logging.getLogger("watchlist.llm.router")

MAX_ATTEMPTS = 3
BASE_BACKOFF = 1.5
MAX_BACKOFF = 20.0
CIRCUIT_THRESHOLD = 3
CIRCUIT_COOLDOWN = 120.0


class TokenBucket:
    """Classic token bucket. `rpm` tokens, refilled continuously."""

    def __init__(self, rpm: int) -> None:
        self.capacity = max(1, rpm)
        self.tokens = float(self.capacity)
        self.refill_per_sec = self.capacity / 60.0
        self.updated = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        self.tokens = min(
            self.capacity, self.tokens + (now - self.updated) * self.refill_per_sec
        )
        self.updated = now

    def try_take(self) -> bool:
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    def wait_seconds(self) -> float:
        self._refill()
        if self.tokens >= 1.0:
            return 0.0
        return (1.0 - self.tokens) / self.refill_per_sec


class CircuitBreaker:
    def __init__(self, threshold: int = CIRCUIT_THRESHOLD,
                 cooldown: float = CIRCUIT_COOLDOWN) -> None:
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at >= self.cooldown:
            # Half-open: let exactly one request through to test the water.
            self.opened_at = None
            self.failures = self.threshold - 1
            return False
        return True

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


@dataclass
class ProviderState:
    provider: object
    rpm: int
    configured_daily_cap: int
    bucket: TokenBucket
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    used_today: int = 0
    observed_daily_cap: int | None = None
    quota_exhausted_until: datetime | None = None
    day: str = ""

    @property
    def name(self) -> str:
        return self.provider.name

    @property
    def daily_cap(self) -> int:
        """Observed beats configured. Free-tier limits move."""
        return self.observed_daily_cap or self.configured_daily_cap

    def roll_day(self, today: str) -> None:
        if self.day != today:
            self.day = today
            self.used_today = 0
            self.quota_exhausted_until = None

    @property
    def quota_blocked(self) -> bool:
        if self.quota_exhausted_until and utc_now() < self.quota_exhausted_until:
            return True
        return self.used_today >= self.daily_cap > 0

    def health_state(self) -> str:
        if not getattr(self.provider, "configured", True):
            return "QUOTA_EXHAUSTED" if self.daily_cap == 0 else "CIRCUIT_OPEN"
        if self.breaker.open:
            return "CIRCUIT_OPEN"
        if self.quota_blocked:
            return "QUOTA_EXHAUSTED"
        if self.bucket.wait_seconds() > 0:
            return "RATE_LIMITED"
        return "OK"


def _midnight_utc() -> datetime:
    return (
        utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        + timedelta(days=1)
    )


class LLMRouter:
    """One instance per process. Holds the cascade and all its guard rails."""

    def __init__(self, providers: list | None = None) -> None:
        if providers is None:
            providers = [GeminiProvider(), OpenRouterProvider()]

        self.states: list[ProviderState] = []
        for p in providers:
            rpm, cap = self._limits_for(p.name)
            self.states.append(
                ProviderState(
                    provider=p,
                    rpm=rpm,
                    configured_daily_cap=cap,
                    bucket=TokenBucket(rpm),
                )
            )

        self.template = TemplateProvider()
        self.template_used_today = 0
        self._day = utc_now().strftime("%Y-%m-%d")

    @staticmethod
    def _limits_for(name: str) -> tuple[int, int]:
        if name == "gemini":
            return settings.gemini_rpm, settings.gemini_rpd
        if name == "openrouter":
            return settings.openrouter_rpm, settings.openrouter_rpd
        return 10, 100

    def _roll(self) -> None:
        today = utc_now().strftime("%Y-%m-%d")
        if today != self._day:
            self._day = today
            self.template_used_today = 0
        for state in self.states:
            state.roll_day(today)

    async def hydrate(self, session: AsyncSession) -> None:
        """Load today's usage from the ledger so a restart does not reset the
        daily budget. Free tiers do not forgive a process that forgets."""
        self._roll()
        usage = await llm_cache.usage_today(session)
        for state in self.states:
            row = usage.get(state.name)
            if row:
                state.used_today = row["calls"]
                if row.get("observed_daily_cap"):
                    state.observed_daily_cap = row["observed_daily_cap"]
        template_row = usage.get("template")
        if template_row:
            self.template_used_today = template_row["calls"]

    # -- the cascade -------------------------------------------------------

    async def _attempt(self, state: ProviderState, coro_factory) -> object:
        """Call one provider with backoff. Raises ProviderError on give-up."""
        last: Exception = ProviderUnavailable("no attempt made")

        for attempt in range(MAX_ATTEMPTS):
            if not state.bucket.try_take():
                wait = state.bucket.wait_seconds()
                # Only wait if it is short. The pipeline is not latency
                # sensitive, but a 40-second stall per item is still a bad trade
                # against just using the next provider.
                if wait > 5.0:
                    raise RateLimited(f"{state.name} bucket empty ({wait:.0f}s)")
                await asyncio.sleep(wait)
                state.bucket.try_take()

            try:
                result = await coro_factory()
            except QuotaExhausted as exc:
                state.quota_exhausted_until = exc.resets_at or _midnight_utc()
                if exc.observed_cap:
                    state.observed_daily_cap = exc.observed_cap
                state.used_today = max(state.used_today, state.daily_cap)
                raise
            except RateLimited as exc:
                last = exc
                delay = exc.retry_after or (BASE_BACKOFF ** (attempt + 1))
                delay = min(delay, MAX_BACKOFF) * (0.7 + random.random() * 0.6)
                log.info("%s rate limited, backing off %.1fs", state.name, delay)
                await asyncio.sleep(delay)
                continue
            except ProviderError as exc:
                last = exc
                state.breaker.record_failure()
                if not exc.retryable:
                    raise
                delay = min(BASE_BACKOFF ** (attempt + 1), MAX_BACKOFF)
                delay *= 0.7 + random.random() * 0.6
                log.info(
                    "%s failed (%s), retry in %.1fs", state.name, exc, delay
                )
                await asyncio.sleep(delay)
                continue
            else:
                state.breaker.record_success()
                state.used_today += 1
                return result

        state.breaker.record_failure()
        raise last

    def _eligible(self, state: ProviderState) -> tuple[bool, str]:
        if not getattr(state.provider, "configured", True):
            return False, "not configured"
        if state.breaker.open:
            return False, "circuit open"
        if state.quota_blocked:
            return False, "daily quota exhausted"
        return True, ""

    async def summarise(
        self, session: AsyncSession, req: SummaryRequest
    ) -> Completion:
        """One summary per symbol-event, shared by every subscriber.

        Cache first — always. Then the cascade. The template at the end is not
        a failure path, it is the guaranteed floor, which is what lets
        `summary_state` be READY rather than UNAVAILABLE with no keys set.
        """
        self._roll()
        content_hash = req.content_hash()

        cached = await llm_cache.get(session, req.symbol, req.event_id, content_hash)
        if cached is not None:
            text, provider = cached
            return Completion(text=text, provider=provider, cached=True)

        await llm_cache.record_miss(session, "router")
        blob = evidence_blob(req.evidence)
        started = time.monotonic()

        for state in self.states:
            ok, why = self._eligible(state)
            if not ok:
                log.debug("skipping %s: %s", state.name, why)
                continue

            try:
                text = await self._attempt(
                    state, lambda s=state: s.provider.summarise(req)
                )
            except ProviderError as exc:
                await llm_cache.record_call(session, state.name, failed=True,
                                            observed_cap=state.observed_daily_cap)
                log.info("cascade: %s unavailable (%s), falling through", state.name, exc)
                continue

            await llm_cache.record_call(session, state.name,
                                        observed_cap=state.observed_daily_cap)

            # The compliance filter runs on generated text, always. A provider
            # that produces advisory language is treated as having failed, not
            # as having produced something we can clean up.
            try:
                clean = compliance.check(str(text), blob)
            except compliance.ComplianceFailure as exc:
                log.warning(
                    "%s output rejected by the compliance filter (%s) — "
                    "falling through to the template",
                    state.name,
                    exc,
                )
                continue

            await llm_cache.put(
                session, req.symbol, req.event_id, content_hash, clean, state.name
            )
            return Completion(
                text=clean,
                provider=state.name,
                latency_ms=(time.monotonic() - started) * 1000.0,
            )

        # -- the floor ------------------------------------------------------
        text = await self.template.summarise(req)
        self.template_used_today += 1
        await llm_cache.record_call(session, "template")
        await llm_cache.put(
            session, req.symbol, req.event_id, content_hash, text, "template"
        )
        return Completion(
            text=text,
            provider="template",
            latency_ms=(time.monotonic() - started) * 1000.0,
        )

    async def check_thesis(self, session: AsyncSession, req: ThesisRequest) -> dict:
        """Contradiction check for one belief cluster. Same cascade, same cache."""
        self._roll()
        content_hash = req.content_hash()
        cache_event = f"thesis:{req.event_id}"

        cached = await llm_cache.get(session, req.symbol, cache_event, content_hash)
        if cached is not None:
            import json

            try:
                parsed = json.loads(cached[0])
                parsed["provider"] = cached[1]
                parsed["cached"] = True
                return parsed
            except (ValueError, TypeError):
                pass

        blob = evidence_blob(req.evidence)

        for state in self.states:
            ok, _ = self._eligible(state)
            if not ok:
                continue
            try:
                verdict = await self._attempt(
                    state, lambda s=state: s.provider.check_thesis(req)
                )
            except ProviderError:
                await llm_cache.record_call(session, state.name, failed=True)
                continue

            await llm_cache.record_call(session, state.name)

            if not compliance.is_compliant(verdict.get("rationale", ""), blob):
                log.warning("%s thesis rationale failed compliance", state.name)
                continue

            verdict["provider"] = state.name
            await self._store_verdict(session, req, cache_event, content_hash, verdict)
            return verdict

        verdict = await self.template.check_thesis(req)
        verdict["provider"] = "template"
        self.template_used_today += 1
        await llm_cache.record_call(session, "template")
        await self._store_verdict(session, req, cache_event, content_hash, verdict)
        return verdict

    async def _store_verdict(self, session, req, cache_event, content_hash, verdict) -> None:
        import json

        await llm_cache.put(
            session,
            req.symbol,
            cache_event,
            content_hash,
            json.dumps(
                {
                    "verdict": verdict["verdict"],
                    "confidence": verdict["confidence"],
                    "rationale": verdict["rationale"],
                }
            ),
            verdict.get("provider", "template"),
        )

    # -- health ------------------------------------------------------------

    def health(self) -> list[ProviderHealth]:
        """Exactly the shape in contracts/fixtures/health.json."""
        self._roll()
        out: list[ProviderHealth] = []

        for state in self.states:
            resets = state.quota_exhausted_until or _midnight_utc()
            out.append(
                ProviderHealth(
                    name=state.name,
                    state=state.health_state(),
                    used_today=state.used_today,
                    daily_cap=state.daily_cap,
                    resets_at=iso(resets),
                )
            )

        out.append(
            ProviderHealth(
                name="template",
                state="OK",
                used_today=self.template_used_today,
                daily_cap=0,          # no cap — it is local and deterministic
                resets_at=None,
            )
        )
        return out

    async def close(self) -> None:
        for state in self.states:
            closer = getattr(state.provider, "close", None)
            if closer:
                await closer()


_router: LLMRouter | None = None


def router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


def set_router(instance: LLMRouter) -> None:
    """Test hook."""
    global _router
    _router = instance
