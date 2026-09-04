"""NVIDIA NIM (build.nvidia.com), over its OpenAI-compatible endpoint.

Third in the cascade, ahead of the template floor. Added after both Gemini
and OpenRouter proved flaky in practice on a real key: Gemini's free-tier
`gemini-flash-latest` returns intermittent 503 "high demand", and OpenRouter's
free-model pool 429s essentially immediately on a fresh key. NVIDIA's NIM
catalog free tier is materially more generous in comparison -- roughly 40
requests/minute against ~1,000-5,000 signup credits, no card -- so it sits
between OpenRouter and the template as a third real chance before falling
back to deterministic prose.

Same shape as openrouter.py deliberately: both are plain chat-completions
POSTs, so there is no reason for the request/response handling to diverge.
Kept as a separate module rather than parameterising openrouter.py because
the two providers' error bodies and header conventions are not the same and
conflating them would make both harder to read.
"""

from __future__ import annotations

import logging

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

log = logging.getLogger("watchlist.llm.nvidia")

ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"


class NvidiaProvider:
    name = "nvidia"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.nvidia_api_key
        self._model = model or settings.nvidia_model
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
                    "Accept": "application/json",
                },
            )
        return self._client

    def _read_limits(self, response: httpx.Response) -> None:
        limit = response.headers.get("X-RateLimit-Limit")
        remaining = response.headers.get("X-RateLimit-Remaining")
        if limit and limit.isdigit():
            self.observed_cap = int(limit)
        if remaining and remaining.isdigit():
            self.observed_remaining = int(remaining)

    async def _chat(self, system: str, user: str, max_tokens: int) -> str:
        if not self._api_key:
            raise ProviderUnavailable("NVIDIA_API_KEY is not set")

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
                f"nvidia transport error: {type(exc).__name__}"
            ) from exc

        self._read_limits(response)

        if response.status_code == 429:
            body = response.text.lower()
            if "credit" in body or "quota" in body:
                raise QuotaExhausted(
                    "nvidia signup credits exhausted", observed_cap=self.observed_cap
                )
            raise RateLimited("nvidia rate limit", retry_after=15.0)

        if response.status_code in (401, 403):
            raise ProviderUnavailable("nvidia auth failure — check NVIDIA_API_KEY")

        if response.status_code == 404:
            raise ProviderUnavailable(f"nvidia model {self._model!r} not found")

        if response.status_code >= 500:
            raise ProviderUnavailable(f"nvidia {response.status_code}")

        if response.status_code != 200:
            raise ProviderUnavailable(
                f"nvidia {response.status_code}: {response.text[:120]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderUnavailable("nvidia returned non-JSON") from exc

        choices = data.get("choices") or []
        if not choices:
            raise ProviderUnavailable("nvidia returned no choices")

        content = (choices[0].get("message") or {}).get("content") or ""
        if not content.strip():
            raise ProviderUnavailable("nvidia returned empty content")
        return content.strip()

    # -- Provider ------------------------------------------------------------

    async def summarise(self, req: SummaryRequest) -> str:
        return await self._chat(SYSTEM_PREFIX, summary_user_turn(req), 220)

    async def check_thesis(self, req: ThesisRequest) -> dict:
        raw = await self._chat(THESIS_SYSTEM_PREFIX, thesis_user_turn(req), 260)
        parsed = parse_verdict(raw)
        if parsed is None:
            raise ProviderUnavailable(
                f"nvidia returned unparseable thesis JSON: {raw[:120]}"
            )
        return parsed

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
