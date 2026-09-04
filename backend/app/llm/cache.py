"""Content-hash cache. Identical inputs must never re-call a provider.

Key: `(symbol, event_id, content_hash)`.

The content hash is over the *evidence*, not over the event id, so two events
that describe the same facts share an entry. That matters more than it sounds:
the ingest pipeline runs every cycle, and without hashing on content, a symbol
whose signals have not changed would burn a free-tier call on every pass and
exhaust 50 requests/day before lunch.

Persisted in Postgres/SQLite rather than only in Redis, because a cache that
empties on restart is not a cache when the daily budget is 50 calls. Redis
fronts it for read latency; the database is the durable copy.

Hit/miss counters live here too and feed `cache_hit_rate_24h` on GET /health —
that number is the honest measure of whether the economic argument in
DESIGN.md §7 is actually holding in this deployment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import utc_now
from ..kv import kv
from ..models import LLMCacheEntry, LLMUsage

log = logging.getLogger("watchlist.llm.cache")

REDIS_TTL = 60 * 60 * 24 * 7  # a week; the DB is the durable copy


def cache_key(symbol: str, event_id: str, content_hash: str) -> str:
    return f"llm:{symbol}:{event_id}:{content_hash}"


async def get(
    session: AsyncSession, symbol: str, event_id: str, content_hash: str
) -> tuple[str, str] | None:
    """Returns `(text, provider)` or None. Checks Redis first, then the DB."""
    key = cache_key(symbol, event_id, content_hash)

    cached = await kv().get(key)
    if isinstance(cached, dict) and cached.get("text"):
        await _bump(session, cached.get("provider", "unknown"), hit=True)
        return cached["text"], cached.get("provider", "unknown")

    row = await session.get(LLMCacheEntry, key)
    if row is not None:
        await kv().set(key, {"text": row.text, "provider": row.provider}, ttl=REDIS_TTL)
        await _bump(session, row.provider, hit=True)
        return row.text, row.provider

    return None


async def put(
    session: AsyncSession,
    symbol: str,
    event_id: str,
    content_hash: str,
    text: str,
    provider: str,
) -> None:
    key = cache_key(symbol, event_id, content_hash)
    now = utc_now()

    existing = await session.get(LLMCacheEntry, key)
    if existing is None:
        session.add(
            LLMCacheEntry(
                key=key,
                symbol=symbol,
                event_id=event_id,
                content_hash=content_hash,
                text=text,
                provider=provider,
                created_at=now,
            )
        )
    else:
        existing.text = text
        existing.provider = provider
        existing.created_at = now

    await session.flush()
    await kv().set(key, {"text": text, "provider": provider}, ttl=REDIS_TTL)


async def record_miss(session: AsyncSession, provider: str) -> None:
    await _bump(session, provider, hit=False)


async def _usage_row(session: AsyncSession, provider: str, day: str) -> LLMUsage:
    found = await session.execute(
        select(LLMUsage).where(LLMUsage.provider == provider, LLMUsage.day == day)
    )
    row = found.scalar_one_or_none()
    if row is None:
        row = LLMUsage(provider=provider, day=day, calls=0, failures=0,
                       cache_hits=0, cache_misses=0)
        session.add(row)
        await session.flush()
    return row


async def _bump(session: AsyncSession, provider: str, hit: bool) -> None:
    day = utc_now().strftime("%Y-%m-%d")
    row = await _usage_row(session, provider, day)
    if hit:
        row.cache_hits += 1
    else:
        row.cache_misses += 1
    await session.flush()


async def hit_rate_24h(session: AsyncSession) -> float:
    """Cache hit rate across the last two UTC day buckets.

    Two buckets rather than a rolling 24h window: the ledger is aggregated
    per day, and a rolling window would need per-call rows for a number that is
    a health indicator, not an accounting record.
    """
    now = utc_now()
    days = {now.strftime("%Y-%m-%d"), (now - timedelta(days=1)).strftime("%Y-%m-%d")}

    rows = await session.execute(select(LLMUsage).where(LLMUsage.day.in_(days)))
    hits = misses = 0
    for row in rows.scalars():
        hits += row.cache_hits
        misses += row.cache_misses

    total = hits + misses
    if total == 0:
        return 0.0
    return round(hits / total, 2)


async def record_call(
    session: AsyncSession, provider: str, failed: bool = False,
    observed_cap: int | None = None,
) -> int:
    """Ledger one provider call. Returns today's running total for that provider."""
    day = utc_now().strftime("%Y-%m-%d")
    row = await _usage_row(session, provider, day)
    row.calls += 1
    if failed:
        row.failures += 1
    if observed_cap is not None:
        row.observed_daily_cap = observed_cap
    await session.flush()
    return row.calls


async def usage_today(session: AsyncSession) -> dict[str, dict]:
    day = utc_now().strftime("%Y-%m-%d")
    rows = await session.execute(select(LLMUsage).where(LLMUsage.day == day))
    return {
        row.provider: {
            "calls": row.calls,
            "failures": row.failures,
            "observed_daily_cap": row.observed_daily_cap,
        }
        for row in rows.scalars()
    }
