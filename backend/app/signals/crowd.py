"""Crowd flow — aggregate watchlist adds/removes as first-party alt-data.

DESIGN.md §2(5): institutions pay for card-transaction panels because they are
proprietary. A broker's structural equivalent is watchlist flow — what retail is
starting and stopping paying attention to — and it is unavailable to anyone who
does not operate the watchlist.

**The privacy rules are enforced here, not documented here.**

*   Minimum cohort of `CROWD_MIN_COHORT` (default 500). Below it, the function
    returns None and no signal exists. There is no override.
*   Aggregate only. `models.WatchFlow` has no `user_id` column at all, so
    "never individual" is a property of the schema rather than a promise about
    this file.
*   The reported figure is a *ratio to trailing median*, never a headcount, so
    the output cannot be differenced across days to recover small cohorts.

This is a confirming factor, never a leading one. Retail attention concentrating
on a symbol is not evidence about the company — treating it as such would be
building the recommendation engine DESIGN.md §9 rules out. It is evidence that
something is going on, which is a claim we can actually support.
"""

from __future__ import annotations

import numpy as np

from ..config import settings
from .base import SignalContext, Signal

TRAILING = 7
MIN_RATIO = 2.5
THRESHOLD_SIGMA = 1.8


def detect(ctx: SignalContext) -> Signal | None:
    if not ctx.flow:
        return None

    rows = sorted(ctx.flow, key=lambda r: r[0])
    latest_session, net_adds, cohort = rows[-1]

    if latest_session != ctx.session_index:
        return None

    # --- the k-anonymity gate. No exceptions, no override. ----------------
    if cohort < settings.crowd_min_cohort:
        return None

    history = np.array([r[1] for r in rows[:-1]][-TRAILING:], dtype=float)
    if history.size < 3:
        return None

    baseline = float(np.median(history))
    if abs(baseline) < 1e-9:
        return None

    ratio = net_adds / baseline
    if ratio < MIN_RATIO:
        return None

    sd = float(np.std(history, ddof=1))
    z = 0.0 if sd < 1e-9 else (net_adds - baseline) / sd
    if abs(z) < THRESHOLD_SIGMA:
        return None

    return Signal(
        kind="CROWD_FLOW",
        z=round(float(z), 2),
        direction="up" if net_adds > 0 else "down",
        detail=(
            f"Net watchlist adds {ratio:.1f}x the trailing weekly median across "
            f"users. Aggregate only, minimum cohort {settings.crowd_min_cohort}."
        ),
        evidence=[
            ctx.evidence(
                "Net adds vs median",
                f"{ratio:.1f}x",
                source="first-party aggregate",
            ),
            ctx.evidence(
                "Cohort size",
                f"{cohort:,} users (k-anonymity floor {settings.crowd_min_cohort:,})",
                source="first-party aggregate",
            ),
        ],
    )
