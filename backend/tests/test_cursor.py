"""The read cursor's only write is max(). This proves the CRDT property
DESIGN.md §4 claims: idempotent, commutative, monotone under any permutation
or duplication of the same ack set."""

from __future__ import annotations

import itertools
import random

import pytest

from app.state.cursor import get_cursor, merge_cursor


@pytest.mark.asyncio
async def test_max_merge_is_idempotent(db_session):
    await merge_cursor(db_session, "u1", "TCS", 100)
    await merge_cursor(db_session, "u1", "TCS", 100)
    assert await get_cursor(db_session, "u1", "TCS") == 100


@pytest.mark.asyncio
async def test_max_merge_never_moves_backwards(db_session):
    await merge_cursor(db_session, "u1", "TCS", 200)
    await merge_cursor(db_session, "u1", "TCS", 50)  # stale ack from an offline device
    assert await get_cursor(db_session, "u1", "TCS") == 200


@pytest.mark.asyncio
async def test_convergence_under_any_permutation(db_session):
    """Every ordering/duplication of the same ack set must converge to the
    same final cursor -- commutativity and idempotence together."""
    values = [40, 10, 90, 60, 60, 30]
    expected = max(values)

    for perm in list(itertools.permutations(values))[:20]:
        symbol = f"SYM{random.randint(0, 1_000_000)}"
        for v in perm:
            await merge_cursor(db_session, "u1", symbol, v)
        assert await get_cursor(db_session, "u1", symbol) == expected
