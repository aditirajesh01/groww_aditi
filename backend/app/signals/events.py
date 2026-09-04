"""Corporate events — discrete, dated facts with a prior on how much they matter.

Earnings, guidance changes, rating actions, block deals, promoter pledges, index
inclusion. Unlike every other detector here, this one does not infer anything
from the price series; it reports something that verifiably happened, with the
filing as its evidence.

That makes it the most valuable *confirming* factor in the set. A large residual
move is interesting; a large residual move on the day of an earnings release
with a margin miss in it is explained. The prior encodes how much a category of
event ought to move a stock at all, so an index-inclusion note does not get
weighted like a guidance cut.

The `payload` becomes evidence verbatim. Nothing in this file paraphrases a
filing — a paraphrase is where an advisory claim would sneak into a system that
promises never to make one.
"""

from __future__ import annotations

from .base import SignalContext, Signal

# How much a category of event is expected to matter, before looking at price.
# These are priors, not predictions: they set the weight the event carries as a
# confirming factor, and they are deliberately conservative.
KIND_PRIORS: dict[str, float] = {
    "earnings": 1.8,
    "guidance": 1.9,
    "rating": 1.2,
    "block_deal": 1.4,
    "pledge": 1.6,
    "index": 1.1,
    "policy": 1.2,
    "other": 1.0,
}

LOOKBACK_SESSIONS = 2   # an event stays "live" for this many sessions


def detect(ctx: SignalContext) -> Signal | None:
    recent = [
        e
        for e in ctx.events
        if 0 <= ctx.session_index - e.session_index <= LOOKBACK_SESSIONS
    ]
    if not recent:
        return None

    event = max(recent, key=lambda e: (e.prior, e.session_index))
    prior = event.prior or KIND_PRIORS.get(event.kind, 1.0)

    payload = event.payload or {}
    direction = payload.get("direction", "neutral")
    if direction not in ("up", "down", "neutral"):
        direction = "neutral"

    evidence = []
    if payload.get("metric") and payload.get("value"):
        evidence.append(
            ctx.evidence(
                str(payload["metric"]),
                str(payload["value"]),
                source=str(payload.get("source", "company filing")),
            )
        )
    if payload.get("consensus"):
        evidence.append(
            ctx.evidence(
                "Consensus estimate",
                str(payload["consensus"]),
                source="street aggregate",
            )
        )
    if event.implied_move_pct:
        evidence.append(
            ctx.evidence(
                "Implied move into the print",
                f"{event.implied_move_pct:.1f}%",
            )
        )
    if not evidence:
        evidence.append(
            ctx.evidence(event.headline, event.kind, source="exchange notice")
        )

    detail = event.headline
    if payload.get("note"):
        detail = f"{event.headline}. {payload['note']}"

    return Signal(
        kind="CORPORATE_EVENT",
        z=round(float(prior), 2),
        direction=direction,
        detail=detail,
        evidence=evidence,
    )
