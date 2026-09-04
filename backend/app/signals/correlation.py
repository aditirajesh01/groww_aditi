"""Correlation break — "TCS and Infosys normally move together; today they didn't."

Interesting only against a genuinely tight baseline. A pair that is normally
0.2 correlated printing 0.05 is noise; a pair that is normally 0.85 printing
0.10 has had something happen to one of them. So the detector requires a strong
baseline before it will speak, and measures the break in Fisher space — the raw
correlation coefficient is bounded and skewed, so a z-score computed on rho
itself over-flags near the extremes where the interesting cases live.

The comparison is against the tightest tracked peer plus the sector aggregate.
Whichever break is larger is what gets reported, because "it decoupled from its
sector" and "it decoupled from its twin" are different stories to a user.
"""

from __future__ import annotations

import numpy as np

from .base import SignalContext, Signal, direction_of
from .stats import correlation, fisher_z

RECENT = 20
BASELINE = 120
MIN_BASELINE_RHO = 0.55
THRESHOLD_SIGMA = 2.0


def _break_z(recent_rho: float, baseline_rho: float, n: int) -> float:
    """Fisher-transformed difference, scaled by its standard error.

    SE of a Fisher z is 1/sqrt(n-3), which is the whole reason to transform:
    it makes the sampling distribution approximately normal and independent of
    the underlying rho.
    """
    if n <= 4:
        return 0.0
    se = 1.0 / np.sqrt(n - 3)
    return float((fisher_z(recent_rho) - fisher_z(baseline_rho)) / se)


def detect(ctx: SignalContext) -> Signal | None:
    if ctx.returns.size < BASELINE + RECENT:
        return None

    candidates: list[tuple[float, str, float, float]] = []  # (z, label, recent, base)

    for peer, peer_returns in ctx.peer_returns.items():
        n = min(ctx.returns.size, peer_returns.size)
        if n < BASELINE + RECENT:
            continue
        mine, theirs = ctx.returns[-n:], peer_returns[-n:]
        baseline_rho = correlation(mine[:-RECENT], theirs[:-RECENT], window=BASELINE)
        if baseline_rho < MIN_BASELINE_RHO:
            continue
        recent_rho = correlation(mine[-RECENT:], theirs[-RECENT:], window=RECENT)
        z = _break_z(recent_rho, baseline_rho, RECENT)
        candidates.append((z, peer, recent_rho, baseline_rho))

    if ctx.sector_returns is not None and ctx.sector_returns.size >= BASELINE + RECENT:
        sector = ctx.sector_returns
        n = min(ctx.returns.size, sector.size)
        mine, theirs = ctx.returns[-n:], sector[-n:]
        baseline_rho = correlation(mine[:-RECENT], theirs[:-RECENT], window=BASELINE)
        if baseline_rho >= MIN_BASELINE_RHO:
            recent_rho = correlation(mine[-RECENT:], theirs[-RECENT:], window=RECENT)
            z = _break_z(recent_rho, baseline_rho, RECENT)
            candidates.append((z, f"{ctx.spec.sector} sector", recent_rho, baseline_rho))

    if not candidates:
        return None

    # Only decoupling is interesting. A pair becoming *more* correlated than
    # usual is not a story anyone needs pushed to them.
    breaks = [c for c in candidates if c[0] < 0]
    if not breaks:
        return None

    z, label, recent_rho, baseline_rho = min(breaks, key=lambda c: c[0])
    if abs(z) < THRESHOLD_SIGMA:
        return None

    detail = (
        f"Normally {baseline_rho:.2f} correlated with {label}; "
        f"realised {recent_rho:.2f} over the last {RECENT} sessions."
    )

    return Signal(
        kind="CORRELATION_BREAK",
        z=round(abs(z), 2),
        direction=direction_of(ctx.last_return * 100.0),
        detail=detail,
        evidence=[
            ctx.evidence(
                f"Rolling {RECENT}d correlation",
                f"{recent_rho:.2f} vs {baseline_rho:.2f} baseline ({label})",
            ),
            ctx.evidence(
                "Baseline window",
                f"{BASELINE} sessions ending {RECENT} sessions ago",
            ),
        ],
    )
