"""Google Gemini free tier — `gemini-2.5-flash` via the `google-genai` SDK.

Free-tier limits move. At time of writing `gemini-2.5-flash` sits around 10 RPM
and somewhere between 250 and 1,500 requests/day depending on what Google
decided that quarter, and it has changed more than once without an announcement.

So this module **treats the live quota as authoritative and the configured
number as a cold start**. When a 429 arrives we parse Google's own quota
metadata out of it — `quotaValue` in the error details, `retryDelay` in the
RetryInfo — and hand the observed cap back to the router, which persists it and
uses it from then on. Hardcoding 500 and believing it is how you end up serving
`UNAVAILABLE` for six hours a day while the budget sits unused, or hammering a
provider that stopped accepting requests two hours ago.

The SDK is an optional dependency. With no `GEMINI_API_KEY`, or with
`google-genai` not installed, `configured` is False and the cascade skips
straight past — a missing key is a deployment choice, not an outage, and it must
not show up as a failure on GET /health.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from ..config import settings
from .base import (
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    SummaryRequest,
    ThesisRequest,
)
from .prompts import (
    SYSTEM_PREFIX,
    THESIS_SYSTEM_PREFIX,
    summary_user_turn,
    thesis_user_turn,
)
from .template import parse_verdict

log = logging.getLogger("watchlist.llm.gemini")

_QUOTA_VALUE = re.compile(r'"quotaValue"\s*:\s*"?(\d+)"?')
_RETRY_DELAY = re.compile(r'"retryDelay"\s*:\s*"?(\d+(?:\.\d+)?)s"?')


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self._model = model or settings.gemini_model
        self._client = None
        self._sdk_missing = False

    @property
    def configured(self) -> bool:
        return bool(self._api_key) and not self._sdk_missing

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from google import genai
        except ImportError:
            self._sdk_missing = True
            raise ProviderUnavailable(
                "google-genai is not installed; `pip install google-genai` to "
                "enable the Gemini provider"
            )
        self._client = genai.Client(api_key=self._api_key)
        return self._client

    # -- error translation -------------------------------------------------

    def _translate(self, exc: Exception) -> Exception:
        """Turn an SDK exception into one of our three provider errors.

        The SDK's exception hierarchy varies by version, so we read the string
        rather than pattern-matching on classes we cannot rely on. Ugly, and
        more robust than the alternative.
        """
        text = str(exc)
        status = getattr(exc, "code", None) or getattr(exc, "status_code", None)

        if "RESOURCE_EXHAUSTED" in text or status == 429 or "429" in text:
            observed = None
            match = _QUOTA_VALUE.search(text)
            if match:
                observed = int(match.group(1))

            retry_after = None
            delay = _RETRY_DELAY.search(text)
            if delay:
                retry_after = float(delay.group(1))

            # Google reports per-minute and per-day exhaustion through the same
            # status. "PerDay" in the quota id is the only reliable separator,
            # and it is the difference between "wait 30s" and "wait until
            # midnight Pacific".
            if "PerDay" in text or "per day" in text.lower():
                resets = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)
                return QuotaExhausted(
                    f"gemini daily quota exhausted{f' (cap {observed})' if observed else ''}",
                    resets_at=resets,
                    observed_cap=observed,
                )
            return RateLimited("gemini rate limit", retry_after=retry_after or 30.0)

        if any(t in text for t in ("PERMISSION_DENIED", "UNAUTHENTICATED", "API key")):
            return ProviderUnavailable(f"gemini auth failure: {text[:120]}")

        return ProviderUnavailable(f"gemini error: {type(exc).__name__}: {text[:120]}")

    async def _generate(self, system: str, user: str, max_tokens: int) -> str:
        client = self._get_client()
        try:
            from google.genai import types
        except ImportError:  # pragma: no cover
            raise ProviderUnavailable("google-genai types unavailable")

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            max_output_tokens=max_tokens,
            # We want the byte-stable prefix above to be the only cacheable
            # thing; nothing volatile is interpolated into it (see prompts.py).
        )

        def call():
            return client.models.generate_content(
                model=self._model, contents=user, config=config
            )

        try:
            # The SDK's sync client is the stable surface; run it off-loop so a
            # slow provider cannot block the event loop the API is served on.
            response = await asyncio.to_thread(call)
        except Exception as exc:
            raise self._translate(exc) from exc

        text = getattr(response, "text", None)
        if not text:
            raise ProviderUnavailable("gemini returned an empty response")
        return text.strip()

    # -- Provider ----------------------------------------------------------

    async def summarise(self, req: SummaryRequest) -> str:
        return await self._generate(SYSTEM_PREFIX, summary_user_turn(req), 220)

    async def check_thesis(self, req: ThesisRequest) -> dict:
        raw = await self._generate(
            THESIS_SYSTEM_PREFIX, thesis_user_turn(req), 260
        )
        parsed = parse_verdict(raw)
        if parsed is None:
            raise ProviderUnavailable(
                f"gemini returned unparseable thesis JSON: {raw[:120]}"
            )
        return parsed
