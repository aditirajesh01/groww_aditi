"""OpenRouter free models, over its OpenAI-compatible endpoint.

Second in the cascade. Free accounts get 20 requests/minute and 50/day across
all `:free` models (1,000/day once an account holds credits, which we assume it
does not).

Two things this module is strict about:

*   **Only `:free` model ids are ever requested.** `_assert_free()` refuses
    anything else before the request leaves the process. A typo in
    `OPENROUTER_MODEL` that silently started billing a reviewer's account would
    be a genuinely bad outcome, and the check costs one line.

*   **The rate-limit headers are believed over the configured constants.**
    OpenRouter returns `X-RateLimit-Limit` / `-Remaining` / `-Reset`, and those
    are the live truth about an account we know nothing about. The configured
    50/day is a cold start only.

Plain httpx, no `openai` SDK — the endpoint is one POST and adding a client
library for it would be a dependency with no payoff.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

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

log = logging.getLogger("watchlist.llm.openrouter")

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class FreeModelRequired(ValueError):
    pass


def _assert_free(model: str) -> str:
    if not model.endswith(":free"):
        raise FreeModelRequired(
            f"refusing to call OpenRouter model {model!r}: this project only "
            f"uses free-tier models, whose ids end in ':free'. Set "
            f"OPENROUTER_MODEL to a ':free' id."
        )
    return model


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.openrouter_api_key
        self._model = _assert_free(model or settings.openrouter_model)
        self._client: httpx.AsyncClient | None = None
        self.observed_cap: int | None = None
        self.observed_remaining: int | None = None

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    # OpenRouter uses these for free-tier attribution.
                    "HTTP-Referer": "https://github.com/groww-challenge/smart-watchlist",
                    "X-Title": "Smart Market Watchlist",
                },
            )
        return self._client

    def _read_limits(self, response: httpx.Response) -> None:
        """Believe the headers over the config. They describe this account."""
        limit = response.headers.get("X-RateLimit-Limit")
        remaining = response.headers.get("X-RateLimit-Remaining")
        if limit and limit.isdigit():
            self.observed_cap = int(limit)
        if remaining and remaining.isdigit():
            self.observed_remaining = int(remaining)

    async def _chat(self, system: str, user: str, max_tokens: int) -> str:
        if not self._api_key:
            raise ProviderUnavailable("OPENROUTER_API_KEY is not set")

        client = await self._http()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }

        try:
            response = await client.post(ENDPOINT, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                f"openrouter transport error: {type(exc).__name__}"
            ) from exc

        self._read_limits(response)

        if response.status_code == 429:
            reset = response.headers.get("X-RateLimit-Reset")
            body = response.text.lower()
            if "per day" in body or "daily" in body or "free-models-per-day" in body:
                resets_at = None
                if reset and reset.isdigit():
                    # OpenRouter sends milliseconds since epoch.
                    resets_at = datetime.fromtimestamp(
                        int(reset) / 1000.0, tz=timezone.utc
                    )
                raise QuotaExhausted(
                    "openrouter daily free quota exhausted",
                    resets_at=resets_at,
                    observed_cap=self.observed_cap,
                )
            raise RateLimited("openrouter rate limit", retry_after=20.0)

        if response.status_code in (401, 403):
            raise ProviderUnavailable("openrouter auth failure — check OPENROUTER_API_KEY")

        if response.status_code >= 500:
            raise ProviderUnavailable(f"openrouter {response.status_code}")

        if response.status_code != 200:
            raise ProviderUnavailable(
                f"openrouter {response.status_code}: {response.text[:120]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("openrouter returned non-JSON") from exc

        # OpenRouter surfaces upstream provider errors inside a 200.
        if isinstance(data.get("error"), dict):
            message = str(data["error"].get("message", ""))[:120]
            if "rate" in message.lower():
                raise RateLimited(f"openrouter upstream: {message}")
            raise ProviderUnavailable(f"openrouter upstream: {message}")

        choices = data.get("choices") or []
        if not choices:
            raise ProviderUnavailable("openrouter returned no choices")

        content = (choices[0].get("message") or {}).get("content") or ""
        if not content.strip():
            raise ProviderUnavailable("openrouter returned empty content")
        return content.strip()

    # -- Provider ----------------------------------------------------------

    async def summarise(self, req: SummaryRequest) -> str:
        return await self._chat(SYSTEM_PREFIX, summary_user_turn(req), 220)

    async def check_thesis(self, req: ThesisRequest) -> dict:
        raw = await self._chat(THESIS_SYSTEM_PREFIX, thesis_user_turn(req), 260)
        parsed = parse_verdict(raw)
        if parsed is None:
            raise ProviderUnavailable(
                f"openrouter returned unparseable thesis JSON: {raw[:120]}"
            )
        return parsed

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
