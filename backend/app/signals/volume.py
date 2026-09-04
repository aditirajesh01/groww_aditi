"""Volume surprise — participation, which is what makes a price move credible.

This detector rarely leads. Its job is to be the *second* factor: a 3-sigma price
move on average volume is frequently one desk rebalancing, while the same move on
3x volume is a lot of people changing their minds at once. That difference is
exactly what the two-factor gate is built to exploit, and it is where the ~45%
false-positive reduction cited in DESIGN.md §1 mostly comes from.

Volume is lognormal-ish, so the z-score is computed on log volume. On raw volume
the distribution's right tail makes every busy day look like a 4-sigma event and
the signal stops discriminating.
"""

from __future__ import annotations

import numpy as np

from .base import SignalContext, Signal
from .stats import zscore

WINDOW = 20
THRESHOLD_SIGMA = 1.8


def detect(ctx: SignalContext) -> Signal | None:
    if ctx.volumes.size < WINDOW + 5:
        return None

    today = float(ctx.volumes[-1])
    history = ctx.volumes[-(WINDOW + 1) : -1]
    if today <= 0 or history.size < WINDOW // 2:
        return None

    log_hist = np.log(np.clip(history, 1.0, None))
    z = zscore(float(np.log(max(today, 1.0))), log_hist)

    if z < THRESHOLD_SIGMA:
        # Unusually *thin* volume is only meaningful next to an expected event,
        # which is absence.py's job, not this one's.
        return None

    average = float(np.mean(history))
    ratio = today / average if average > 0 else 0.0

    return Signal(
        kind="VOLUME_SURPRISE",
        z=round(z, 2),
        direction="up",
        detail=(
            f"{ratio:.1f}x {WINDOW}-day average volume — the move has "
            f"participation behind it."
        ),
        evidence=[
            ctx.evidence(f"Volume vs {WINDOW}d avg", f"{ratio:.1f}x"),
            ctx.evidence("Session volume", f"{today:,.0f} shares"),
            ctx.evidence("Participation z-score", f"{z:.1f}σ (log scale)"),
        ],
    )
