"""Real NSE quotes via Yahoo Finance.

No API key and no `yfinance` dependency — this is two documented chart/quote
endpoints and ~150 lines of httpx, which is less code than the wrapper library
and does not pull pandas in behind it.

This adapter is honest about being best-effort. Yahoo rate-limits aggressively,
occasionally returns HTML instead of JSON, and is delayed by ~15 minutes on NSE.
Every one of those shows up as a freshness downgrade rather than an exception,
because the whole point of the reconciler is that a degraded source degrades the
label, not the page.

`FEED_ADAPTER=yahoo` opts in. The default stays `simulator`, so a reviewer with
no network still gets a working demo.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from ..config import settings
from ..universe import BY_SYMBOL
from .base import BarPoint, CorpAction, MarketEvent, Quote

log = logging.getLogger("watchlist.yahoo")

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class YahooAdapter:
    """Best-effort real quotes. Never raises into the pipeline."""

    name = "yahoo"

    def __init__(self, timeout: float = 6.0) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._fail_streak = 0

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout, headers=HEADERS, follow_redirects=True
            )
        return self._client

    def _ticker(self, symbol: str) -> str:
        s = BY_SYMBOL.get(symbol)
        return s.yahoo_ticker if s else f"{symbol}.NS"

    async def _chart(self, symbol: str, rng: str, interval: str) -> dict | None:
        client = await self._http()
        url = CHART_URL.format(ticker=self._ticker(symbol))
        try:
            resp = await client.get(url, params={"range": rng, "interval": interval})
            if resp.status_code == 429:
                self._fail_streak += 1
                log.warning("yahoo rate-limited on %s", symbol)
                return None
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            self._fail_streak += 1
            log.warning("yahoo fetch failed for %s: %s", symbol, type(exc).__name__)
            return None

        self._fail_streak = 0
        result = (payload.get("chart") or {}).get("result") or []
        return result[0] if result else None

    async def quote(self, symbol: str, source_id: int = 0) -> Quote | None:
        data = await self._chart(symbol, "5d", "1d")
        if not data:
            return None
        meta = data.get("meta") or {}
        last = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if last is None or prev is None:
            return None

        ts = meta.get("regularMarketTime")
        as_of = (
            datetime.fromtimestamp(ts, tz=timezone.utc)
            if ts
            else datetime.now(timezone.utc)
        )

        volume = 0.0
        quotes = ((data.get("indicators") or {}).get("quote") or [{}])[0]
        vols = [v for v in (quotes.get("volume") or []) if v]
        if vols:
            volume = float(vols[-1])

        return Quote(
            symbol=symbol,
            last=float(last),
            prev_close=float(prev),
            volume=volume,
            as_of=as_of,
            source=self.name,
            session_index=0,
        )

    async def quotes(self, symbols: list[str], source_id: int = 0) -> dict[str, Quote]:
        # Yahoo's batch quote endpoint now requires a crumb/cookie dance that is
        # not worth the fragility, so we fan out with bounded concurrency.
        sem = asyncio.Semaphore(8)

        async def one(sym: str) -> tuple[str, Quote | None]:
            async with sem:
                return sym, await self.quote(sym)

        pairs = await asyncio.gather(*(one(s) for s in symbols))
        return {s: q for s, q in pairs if q is not None}

    async def history(self, symbol: str, sessions: int) -> list[BarPoint]:
        rng = "1y" if sessions > 130 else "6mo" if sessions > 60 else "3mo"
        data = await self._chart(symbol, rng, "1d")
        if not data:
            return []

        stamps = data.get("timestamp") or []
        quotes = ((data.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quotes.get("close") or []
        volumes = quotes.get("volume") or []

        bars: list[BarPoint] = []
        for i, (ts, close) in enumerate(zip(stamps, closes)):
            if close is None:
                continue
            bars.append(
                BarPoint(
                    symbol=symbol,
                    session_index=i,
                    ts=datetime.fromtimestamp(ts, tz=timezone.utc),
                    close=float(close),
                    volume=float(volumes[i] or 0.0) if i < len(volumes) else 0.0,
                )
            )
        return bars[-sessions:]

    async def corporate_actions(
        self, symbol: str, session: int | None = None
    ) -> list[CorpAction]:
        """Yahoo exposes splits/dividends on the chart endpoint with
        `events=div,split`. We deliberately do not use it here.

        Mapping a Unix ex-timestamp onto our session index is only meaningful
        when both sides come from the same calendar, and mixing a real ex-date
        into a simulated session index would produce an adjustment that is
        wrong in a way nobody would notice. Returning nothing is the honest
        answer: with FEED_ADAPTER=yahoo, corporate actions come from the
        simulator's action calendar, which is where the demo scenarios live.
        """
        return []

    async def corporate_events(self, symbol: str) -> list[MarketEvent]:
        """Earnings dates and rating actions need a news/fundamentals feed that
        is not free. The simulator supplies these; see the note above."""
        return []

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def healthy(self) -> bool:
        return self._fail_streak < 3
