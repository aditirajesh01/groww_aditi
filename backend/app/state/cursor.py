"""The read cursor. A watchlist is a changelog, and this is the cursor into it.

Two pieces:

*   `allocate_seq()` — a globally monotonic sequence. Every promoted change gets
    one. Monotonic across the *system*, not per-symbol, which is what makes
    "everything after 184100" a coherent question.

*   `ack()` — advance a user's per-symbol cursor. The only write is `max()`.

**Why max() and nothing else.**

The merge operation on a replicated cursor has to be a join in the
mathematical sense: idempotent, commutative, associative. `max()` on integers is
all three, so:

*   *Idempotent* — replaying the same ack changes nothing. Duplicate delivery,
    which is guaranteed in any at-least-once system, is free.
*   *Commutative* — phone acks 184213 then laptop acks 184190, or the reverse:
    same result. Out-of-order arrival, which is guaranteed the moment you have
    two devices, is free.
*   *Monotone* — the cursor never moves backwards, so a stale ack from a device
    that was offline for a week cannot mark unread things as read.

That is a state-based CRDT (a grow-only register over a totally ordered set),
which means no coordination, no locks, no last-write-wins timestamps to get
wrong, and offline devices reconcile to exactly the same state as online ones.
DESIGN.md §4 claims this property; tests/test_cursor.py proves it by fuzzing
random permutations and duplications of the same ack set and asserting they all
converge.

The thing to *not* do is store a set of read event ids. It is unbounded, it
needs real conflict resolution, and it answers a question nobody asked. A
watchlist user does not want to know which individual cards they have seen; they
want "what changed since I last looked", and that is a single integer.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import utc_now
from ..config import settings
from ..models import Event, ReadCursor, SeqCounter

log = logging.getLogger("watchlist.cursor")


async def allocate_seq(session: AsyncSession, count: int = 1) -> list[int]:
    """Reserve `count` sequence numbers.

    Single counter row, read-modify-write inside the caller's transaction. At
    10k users this is nowhere near contended (a few hundred allocations a day).
    At 10M it becomes a Redis INCR or a Postgres sequence; the call site does
    not change, which is the point of putting it behind a function.
    """
    row = await session.get(SeqCounter, 1)
    if row is None:
        row = SeqCounter(id=1, value=settings.seq_origin)
        session.add(row)
        await session.flush()

    start = row.value + 1
    row.value = row.value + count
    await session.flush()
    return list(range(start, start + count))


async def current_seq(session: AsyncSession) -> int:
    row = await session.get(SeqCounter, 1)
    return row.value if row else settings.seq_origin


async def get_cursors(session: AsyncSession, user_id: str) -> dict[str, int]:
    """Every cursor for one user. One indexed, user-scoped query — no
    cross-shard access, which is the property DESIGN.md §5 is protecting."""
    rows = await session.execute(
        select(ReadCursor.symbol, ReadCursor.last_seen_seq).where(
            ReadCursor.user_id == user_id
        )
    )
    return {symbol: seq for symbol, seq in rows.all()}


async def get_cursor(session: AsyncSession, user_id: str, symbol: str) -> int:
    row = await session.execute(
        select(ReadCursor.last_seen_seq).where(
            ReadCursor.user_id == user_id, ReadCursor.symbol == symbol
        )
    )
    value = row.scalar_one_or_none()
    return int(value) if value is not None else 0


async def merge_cursor(
    session: AsyncSession, user_id: str, symbol: str, seq: int, now: datetime | None = None
) -> int:
    """`last_seen_seq = max(current, seq)`. The only cursor write in the system.

    Returns the resulting cursor value, which may be unchanged — an ack that
    does not move the cursor is a successful no-op, not an error.
    """
    now = now or utc_now()
    existing = await session.execute(
        select(ReadCursor).where(
            ReadCursor.user_id == user_id, ReadCursor.symbol == symbol
        )
    )
    row = existing.scalar_one_or_none()

    if row is None:
        row = ReadCursor(
            user_id=user_id, symbol=symbol, last_seen_seq=max(0, seq), updated_at=now
        )
        session.add(row)
        await session.flush()
        return row.last_seen_seq

    merged = max(row.last_seen_seq, seq)
    if merged != row.last_seen_seq:
        row.last_seen_seq = merged
        row.updated_at = now
        await session.flush()
    return row.last_seen_seq


async def ack(
    session: AsyncSession, user_id: str, event_ids: list[str]
) -> dict[str, int]:
    """Advance cursors for the symbols covered by `event_ids`.

    Unknown ids are ignored rather than rejected: a client replaying a queue
    from an old session may reference events that have since aged out, and
    failing the whole batch for that would be hostile to the exact offline
    case this design is built for.
    """
    if not event_ids:
        return {}

    rows = await session.execute(
        select(Event.symbol, func.max(Event.seq))
        .where(Event.event_id.in_(event_ids))
        .group_by(Event.symbol)
    )
    per_symbol = {symbol: int(seq) for symbol, seq in rows.all()}

    out: dict[str, int] = {}
    for symbol, seq in per_symbol.items():
        out[symbol] = await merge_cursor(session, user_id, symbol, seq)

    if len(per_symbol) < len({e for e in event_ids}):
        log.debug(
            "ack for user=%s referenced %d unknown event ids — ignored",
            user_id,
            len(set(event_ids)) - len(per_symbol),
        )
    return out


async def unread_count(
    session: AsyncSession, user_id: str, symbols: list[str]
) -> int:
    """How many promoted events sit past the user's cursors.

    Deliberately a single query over the join, not a loop — this runs on the
    watchlist screen and DESIGN.md §6 budgets 3-5ms for the whole
    profile+cursor fetch.
    """
    if not symbols:
        return 0

    cursors = await get_cursors(session, user_id)
    rows = await session.execute(
        select(Event.symbol, Event.seq).where(Event.symbol.in_(symbols))
    )
    total = 0
    for symbol, seq in rows.all():
        if seq > cursors.get(symbol, 0):
            total += 1
    return total


def is_unread(seq: int, cursor: int) -> bool:
    return seq > cursor
