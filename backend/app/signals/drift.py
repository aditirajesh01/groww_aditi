"""Drift — the slow move no threshold alert will ever catch.

DESIGN.md calls this the most under-served signal in every watchlist product,
and the arithmetic is why: 0.4% a day for three weeks is 8%, and not one of
those sessions trips a 2%, 3% or 5% rule. The user checks in, sees "-0.3% today",
and has no idea their position has quietly lost a tenth of its value since they
last looked.

The detector looks for the conjunction that defines drift:

    cumulative move is large   AND   no single session was large

The second clause is what stops this from double-counting a crash. A stock that
fell 9% in one session and drifted sideways afterwards is an IDIOSYNCRATIC_MOVE,
not a drift, and firing both would be two "independent" confirmations of the
same fact — which is precisely the failure mode the two-factor gate exists to
prevent. Independence has to be real or the gate is theatre.
"""

from __future__ import annotations

import numpy as np

from .base import SignalContext, Signal, direction_of
from .stats import realised_vol

MIN_SESSIONS = 10
MAX_SESSIONS = 25
# A session bigger than this would have tripped a conventional alert already.
SINGLE_SESSION_CAP_PCT = 1.5
MIN_CUMULATIVE_PCT = 4.0
THRESHOLD_SIGMA = 2.0


def detect(ctx: SignalContext) -> Signal | None:
    if ctx.returns.size < MAX_SESSIONS + 20:
        return None

    best: tuple[float, int, float, float] | None = None  # (|z|, n, cum, largest)

    for n in range(MIN_SESSIONS, MAX_SESSIONS + 1):
        window = ctx.returns[-n:]
        cumulative = (float(np.prod(1.0 + window)) - 1.0) * 100.0
        largest = float(np.max(np.abs(window))) * 100.0

        if abs(cumulative) < MIN_CUMULATIVE_PCT:
            continue
        if largest > SINGLE_SESSION_CAP_PCT:
            continue

        # Scale the cumulative move by what a random walk of this length would
        # be expected to produce, using the *pre-window* volatility so the drift
        # itself does not inflate its own denominator.
        baseline = ctx.returns[: -n] if ctx.returns.size > n else ctx.returns
        sigma_daily = realised_vol(baseline, window=60) / np.sqrt(252.0)
        if sigma_daily < 1e-9:
            continue
        expected = sigma_daily * np.sqrt(n) * 100.0
        z = cumulative / expected

        if best is None or abs(z) > abs(best[0]):
            best = (z, n, cumulative, largest)

    if best is None or abs(best[0]) < THRESHOLD_SIGMA:
        return None

    z, n, cumulative, largest = best
    median = float(np.median(ctx.returns[-n:])) * 100.0

    detail = (
        f"Median daily move {median:+.2f}% across {n} sessions. "
        f"No single day exceeded {largest:.2f}%. Cumulative {cumulative:+.1f}%."
    )

    return Signal(
        kind="DRIFT",
        z=round(z, 2),
        direction=direction_of(z),
        detail=detail,
        evidence=[
            ctx.evidence(f"Cumulative {n}d return", f"{cumulative:+.1f}%"),
            ctx.evidence("Largest single-day move", f"{largest:.2f}%"),
            ctx.evidence(
                "Expected range for the window",
                f"±{abs(cumulative / z):.1f}% at 1σ",
            ),
        ],
    )
