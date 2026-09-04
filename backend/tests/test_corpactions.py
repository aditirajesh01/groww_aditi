"""Corporate-action adjustment is the top correctness risk in the backend
(see ingest/corpactions.py's module docstring): an unadjusted 1:5 split reads
as an 80% single-session loss and the two-factor gate waves it straight
through. This proves adjustment neutralises it, and that the correction path
fires when a notice arrives late."""

from __future__ import annotations

from app.ingest.base import CorpAction
from app.ingest.corpactions import adjust_closes, restatement


def test_unadjusted_split_would_look_like_a_crash():
    """Sanity check on the fixture itself: without adjustment a 1:5 split
    really does look like an 80% crash, which is why adjustment is mandatory."""
    raw = [100.0, 100.0, 20.0, 20.0]  # ex-date at index 2, price divided by 5
    drop_pct = (raw[2] / raw[1] - 1.0) * 100.0
    assert drop_pct < -75.0


def test_adjustment_neutralises_a_split():
    raw = [100.0, 100.0, 20.0, 20.0]
    idxs = [0, 1, 2, 3]
    action = CorpAction(symbol="X", kind="split", ex_session=2, known_at_session=2,
                        ratio_from=1.0, ratio_to=5.0, description="1:5 split")
    adjusted, was_adjusted = adjust_closes(raw, idxs, [action], known_as_of=2)

    assert was_adjusted
    # The adjusted series should be flat across the ex-date -- no fake crash.
    session_return = (adjusted[2] / adjusted[1] - 1.0) * 100.0
    assert abs(session_return) < 1.0


def test_action_not_yet_known_is_not_applied():
    """A notice that has not arrived cannot be applied -- this gap is exactly
    how an unadjusted print reaches a user, and it is what makes a correction
    possible later."""
    raw = [100.0, 100.0, 20.0, 20.0]
    idxs = [0, 1, 2, 3]
    action = CorpAction(symbol="X", kind="split", ex_session=2, known_at_session=3,
                        ratio_from=1.0, ratio_to=5.0, description="1:5 split")
    adjusted, was_adjusted = adjust_closes(raw, idxs, [action], known_as_of=2)

    assert not was_adjusted
    assert adjusted == raw


def test_late_notice_triggers_a_restatement():
    raw = [100.0, 100.0, 20.0, 20.0]
    idxs = [0, 1, 2, 3]
    action = CorpAction(symbol="X", kind="split", ex_session=2, known_at_session=3,
                        ratio_from=1.0, ratio_to=5.0, description="1:5 split")

    # What we would have published at session 2, before the notice arrived.
    published_pct = (raw[2] / raw[1] - 1.0) * 100.0  # ~ -80%

    r = restatement(
        symbol="X", session_index=2, published_pct=published_pct,
        raw_closes=raw, session_indices=idxs, actions=[action], known_as_of=3,
    )
    assert r is not None
    assert abs(r.corrected_pct) < 1.0
    assert r.delta_pct > 50.0  # the restatement materially changes the story
