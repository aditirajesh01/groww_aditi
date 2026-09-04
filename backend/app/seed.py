"""Demo watchlist seeding.

Every new user (one per browser `device_id` — see api/deps.py) is seeded with a
watchlist reproducing the eight scenarios `ingest/simulator.py` encodes at the
sim epoch (see `SCENARIO_NOTES`). That is a deliberate choice for a judged demo:
whoever opens the hosted URL, on whatever device, sees a live, populated
product on the very first `GET /digest` rather than an empty state that only
works if someone remembers to click "add" first.

Theses are written in the same plain language DESIGN.md §2(2) describes, and
they are what makes the Tata Motors card a *contradiction* rather than a
generic alert: the system is checking this text against dated evidence, not
against a threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from .clock import utc_now
from .llm.embed import best_embed
from .models import User, WatchItem


@dataclass(frozen=True)
class DemoWatch:
    symbol: str
    thesis: str | None
    qty: float | None = None
    avg_cost: float | None = None


DEMO_WATCHES: tuple[DemoWatch, ...] = (
    DemoWatch("TATAMOTORS", "watching for margin recovery in JLR", qty=50, avg_cost=780.0),
    DemoWatch("SUNPHARMA", "waiting for specialty-portfolio margin expansion", qty=30, avg_cost=1750.0),
    DemoWatch("HDFCBANK", "core long-term banking holding", qty=20, avg_cost=1900.0),
    DemoWatch("INFY", "watching FY27 guidance reiteration play out", qty=15, avg_cost=1600.0),
    DemoWatch("WIPRO", None, qty=200, avg_cost=260.0),
    DemoWatch("ETERNAL", "want it under 240 before adding", qty=None, avg_cost=None),
    DemoWatch("TCS", None, qty=10, avg_cost=3150.0),
    DemoWatch("DMART", None, qty=None, avg_cost=None),
)


async def seed_watchlist_for(session: AsyncSession, user: User) -> None:
    now = utc_now()
    for w in DEMO_WATCHES:
        item = WatchItem(
            user_id=user.id,
            symbol=w.symbol,
            thesis=w.thesis,
            thesis_added_at=now if w.thesis else None,
            thesis_vector=best_embed(w.thesis) if w.thesis else None,
            qty=w.qty,
            avg_cost=w.avg_cost,
            muted_kinds=[],
            open_count=0,
            added_at=now,
        )
        session.add(item)
    await session.flush()
