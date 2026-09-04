"""Corporate-action adjustment. This runs BEFORE change detection, always.

This is the single most important correctness detail in the backend.

An unadjusted 1:5 split prints as a 80% single-session loss. Every downstream
detector then agrees enthusiastically: the idiosyncratic residual is 40 sigma,
the volume z-score is enormous, the changepoint posterior pins to 1.0. Three
independent confirmations, so the two-factor gate — which exists precisely to
stop false positives — waves it straight through, and 10,000 people get paged
about a crash that did not happen. A gate cannot save you from bad input; it
amplifies it. The only defence is adjusting first.

Two functions, deliberately pure:

  adjust_closes()  raw quoted series + known actions -> continuous series
  restatement()    what we published before vs what it should have been

`restatement()` is what makes corrections possible. Corrections are append-only
(DESIGN.md §8): we never rewrite the old number, because a user may have acted
on it. We publish the correction next to it and say so.
"""

from __future__ import annotations

from dataclasses import dataclass

from .base import CorpAction


def applicable(actions: list[CorpAction], known_as_of: int) -> list[CorpAction]:
    """The subset of actions we have actually been notified of.

    A notice that has not arrived cannot be applied. This is not pedantry: the
    gap between `ex_session` and `known_at_session` is exactly how an
    unadjusted print reaches a user in production.
    """
    return [a for a in actions if a.known_at_session <= known_as_of]


def cumulative_factor(actions: list[CorpAction], session_index: int) -> float:
    """Product of the price factors of every action with an ex-date after
    `session_index`. Multiply a quoted price from that session by this to put
    it on today's share-count scale."""
    factor = 1.0
    for a in actions:
        if session_index < a.ex_session:
            factor *= a.price_factor
    return factor


def adjust_closes(
    closes: list[float],
    session_indices: list[int],
    actions: list[CorpAction],
    known_as_of: int | None = None,
) -> tuple[list[float], bool]:
    """Back-adjust a quoted series onto a single continuous scale.

    Returns `(adjusted, was_adjusted)`. `was_adjusted` is False when no known
    action touches the window — that flag becomes
    `Provenance.corporate_action_adjusted`, so a user can always see whether
    the number in front of them went through this path.
    """
    known = applicable(actions, known_as_of) if known_as_of is not None else list(actions)
    if not known:
        return list(closes), False

    touched = False
    out: list[float] = []
    for idx, close in zip(session_indices, closes, strict=True):
        factor = cumulative_factor(known, idx)
        if factor != 1.0:
            touched = True
        out.append(close * factor)

    # Cash dividends shift the level rather than rescaling it. Applied after
    # the multiplicative pass so a dividend and a split in the same window
    # compose in the right order.
    for a in known:
        if a.kind == "dividend" and a.cash_amount:
            out = [
                c - a.cash_amount if idx < a.ex_session else c
                for idx, c in zip(session_indices, out, strict=True)
            ]
            touched = True

    return out, touched


def session_return_pct(closes: list[float], at: int = -1) -> float:
    """Session-over-session return of an already-adjusted series."""
    if len(closes) < 2:
        return 0.0
    prev = closes[at - 1]
    if prev == 0:
        return 0.0
    return (closes[at] / prev - 1.0) * 100.0


@dataclass(frozen=True)
class Restatement:
    """A previously published number that is now known to have been wrong."""

    symbol: str
    session_index: int
    published_pct: float
    corrected_pct: float
    action: CorpAction

    @property
    def delta_pct(self) -> float:
        return self.corrected_pct - self.published_pct

    @property
    def description(self) -> str:
        return (
            f"{self.action.description or self.action.kind}, "
            f"ex-date session {self.action.ex_session}"
        )


def restatement(
    symbol: str,
    session_index: int,
    published_pct: float,
    raw_closes: list[float],
    session_indices: list[int],
    actions: list[CorpAction],
    known_as_of: int,
    tolerance_pct: float = 0.5,
) -> Restatement | None:
    """Did a late-arriving corporate action invalidate something we published?

    Called on every ingest cycle for sessions we have already reported on. If a
    notice arrived after we printed a number, this is where we find out.
    """
    known = applicable(actions, known_as_of)
    late = [
        a
        for a in known
        if a.ex_session <= session_index and a.known_at_session > a.ex_session
    ]
    if not late:
        return None

    adjusted, _ = adjust_closes(raw_closes, session_indices, known, known_as_of)
    try:
        pos = session_indices.index(session_index)
    except ValueError:
        return None
    if pos == 0:
        return None

    corrected = (adjusted[pos] / adjusted[pos - 1] - 1.0) * 100.0
    if abs(corrected - published_pct) < tolerance_pct:
        return None

    return Restatement(
        symbol=symbol,
        session_index=session_index,
        published_pct=round(published_pct, 2),
        corrected_pct=round(corrected, 2),
        action=late[0],
    )
