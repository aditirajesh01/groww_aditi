"""Absence — expected to move, and didn't.

The signal nobody ships, because a system built around thresholds structurally
cannot see it: nothing crossed anything, so there is nothing to fire on.

But "Infosys reported and the stock did not move" is real information. It says
the market had already priced the result, which is a different state of the
world from "Infosys has not reported yet", and a user who checks in a week later
cannot distinguish the two without being told. An empty week and a week where
the thing you were waiting for happened and changed nothing look identical on a
price chart.

Mechanically: we had an expectation (the implied move into a scheduled event),
and the realised move came in far under it. The z-score is negative by
convention — the surprise is the *shortfall* — and `direction` stays neutral
because a non-move has no direction.
"""

from __future__ import annotations

import numpy as np

from .base import SignalContext, Signal
from .stats import realised_vol

# The realised move must be this far under the implied one to count.
MIN_SHORTFALL_RATIO = 0.35
THRESHOLD_SIGMA = 1.6


def detect(ctx: SignalContext) -> Signal | None:
    event = ctx.event_at(ctx.session_index)
    if event is None or not getattr(event, "implied_move_pct", 0.0):
        return None

    implied = float(event.implied_move_pct)
    realised = abs(ctx.last_return) * 100.0

    if implied <= 0:
        return None
    if realised > implied * MIN_SHORTFALL_RATIO:
        return None

    # Scale the shortfall by the stock's ordinary daily sigma, so "didn't move"
    # means something different for ETERNAL than it does for NESTLEIND.
    daily_sigma = realised_vol(ctx.returns, window=60) / np.sqrt(252.0) * 100.0
    if daily_sigma < 1e-9:
        return None

    z = -abs(implied - realised) / daily_sigma
    if abs(z) < THRESHOLD_SIGMA:
        return None

    detail = (
        f"Event-day realised move {realised:.1f}% against a {implied:.1f}% "
        f"implied. Expected volatility did not materialise."
    )

    return Signal(
        kind="ABSENCE",
        z=round(z, 2),
        direction="neutral",
        detail=detail,
        evidence=[
            ctx.evidence(
                "Implied vs realised",
                f"{implied:.1f}% implied / {realised:.1f}% realised",
            ),
            ctx.evidence("Scheduled event", event.headline, source="company filing"),
            ctx.evidence(
                "Ordinary daily move", f"{daily_sigma:.2f}% (1σ, 60 sessions)"
            ),
        ],
    )
