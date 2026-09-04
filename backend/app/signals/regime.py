"""Regime change — online changepoint detection on realised volatility.

A slow truth that is invisible to a chart glance: the price may be flat, but if
daily swings have doubled, the thing you own is not the thing you bought. That
is worth telling someone, and no price threshold will ever say it.

We run BOCPD (Adams & MacKay) on **log** realised volatility with a constant
hazard of 1/250. Two modelling notes, since both are load-bearing:

*   *Log* vol, because volatility is multiplicative and right-skewed. On raw
    vol the Gaussian observation model would read every quiet stretch as a
    downward changepoint.
*   *Unknown variance* (Normal-Gamma prior, Student-t predictive), because the
    variance of log-vol is itself regime-dependent. Assuming it known is the
    usual way BOCPD gets over-confident on financial series.

The signal reports the posterior probability directly, which is the honest
output of a Bayesian model and reads better to a user than a synthetic score:
"0.87 probability the regime broke on 26 August" is checkable. `stats.cusum()`
is kept alongside as a simple second opinion — DESIGN.md allows a well-commented
CUSUM as the fallback, and having both means the BOCPD posterior can be sanity
checked rather than trusted blindly.
"""

from __future__ import annotations

import numpy as np

from .base import SignalContext, Signal
from .stats import TRADING_DAYS, bocpd

VOL_WINDOW = 10          # sessions per realised-vol estimate
HAZARD = 1.0 / 250.0     # ~one regime change per trading year
MIN_POSTERIOR = 0.55
MIN_VOL_RATIO = 1.5      # ignore statistically real but trivial shifts


def _rolling_vol_series(returns: np.ndarray, window: int) -> np.ndarray:
    """Trailing annualised realised vol at each point."""
    if returns.size < window + 1:
        return np.zeros(0)
    out = np.empty(returns.size - window + 1)
    for i in range(out.size):
        chunk = returns[i : i + window]
        out[i] = float(np.std(chunk, ddof=1)) * np.sqrt(TRADING_DAYS)
    return out


def detect(ctx: SignalContext) -> Signal | None:
    if ctx.returns.size < 80:
        return None

    vol = _rolling_vol_series(ctx.returns, VOL_WINDOW)
    if vol.size < 40:
        return None

    log_vol = np.log(np.clip(vol, 1e-6, None))
    result = bocpd(log_vol, hazard=HAZARD, recent_window=12)

    if result.probability < MIN_POSTERIOR or result.index is None:
        return None

    vol_before = float(np.exp(result.before)) * 100.0
    vol_after = float(np.exp(result.after)) * 100.0
    if vol_before < 1e-6:
        return None

    ratio = vol_after / vol_before
    if ratio < MIN_VOL_RATIO and ratio > 1.0 / MIN_VOL_RATIO:
        return None

    # Map the changepoint index in the vol series back to a session index.
    break_session = ctx.session_index - (vol.size - 1 - result.index)

    # z is reported as a monotone transform of the posterior so it lives on the
    # same axis as every other signal for the scoring layer. The posterior is
    # the honest quantity and it is the one shown to the user.
    z = float(np.clip(result.probability * 3.0, 0.0, 3.0))

    direction = "neutral"  # a vol regime change has no price direction
    detail = (
        f"BOCPD posterior {result.probability:.2f} for a changepoint around "
        f"session {break_session}. Realised {VOL_WINDOW}-day volatility "
        f"{vol_before:.1f}% → {vol_after:.1f}% annualised."
    )

    return Signal(
        kind="REGIME_CHANGE",
        z=round(z, 2),
        direction=direction,
        detail=detail,
        evidence=[
            ctx.evidence(
                "Changepoint posterior",
                f"{result.probability:.2f} @ session {break_session}",
            ),
            ctx.evidence(
                f"Realised volatility ({VOL_WINDOW}d, annualised)",
                f"{vol_before:.1f}% → {vol_after:.1f}%",
            ),
            ctx.evidence("Hazard rate", f"{HAZARD:.4f} (~1 per 250 sessions)"),
        ],
    )
