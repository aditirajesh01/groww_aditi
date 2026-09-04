"""Idiosyncratic move — the beta-stripped residual, in sigma.

The most useful signal in the set, and the one every threshold alert gets wrong.

On a day when NIFTY is down 2%, a high-beta auto name being down 2.4% is not
news about that company; it is the index, arriving on schedule. Conversely a
0.9% fall in a low-beta FMCG name on a day the index rose can be a 3-sigma
company-specific event that no `abs(pct) > 5` rule will ever see.

So we fit `r_stock = alpha + beta * r_index` over a rolling 60 sessions and
report the residual, scaled by the residual standard deviation. Two consequences
fall out for free:

*   A 3% move in a stable large-cap and a 3% move in a volatile smallcap get
    scored differently, because they are divided by different sigmas.
*   The number we show a user — "5.4% of the 6.2% fall is idiosyncratic" — is
    directly interpretable, which matters for the evidence trail.
"""

from __future__ import annotations

from .base import SignalContext, Signal, direction_of
from .stats import rolling_ols

WINDOW = 60
THRESHOLD_SIGMA = 2.0


def detect(ctx: SignalContext) -> Signal | None:
    if not ctx.enough_history:
        return None

    fit = rolling_ols(ctx.returns, ctx.index_returns, window=WINDOW)
    r_stock = ctx.last_return
    r_index = ctx.last_index_return

    residual = fit.residual(r_stock, r_index)
    z = fit.residual_z(r_stock, r_index)

    if abs(z) < THRESHOLD_SIGMA:
        return None

    raw_pct = r_stock * 100.0
    resid_pct = residual * 100.0
    explained_pct = (fit.beta * r_index) * 100.0

    detail = (
        f"{'Down' if raw_pct < 0 else 'Up'} {abs(raw_pct):.1f}% raw; "
        f"{abs(resid_pct):.1f}% of that is idiosyncratic after stripping a "
        f"{fit.beta:.2f} index beta."
    )

    return Signal(
        kind="IDIOSYNCRATIC_MOVE",
        z=round(z, 2),
        direction=direction_of(z),
        detail=detail,
        evidence=[
            ctx.evidence(
                "Beta-adjusted residual",
                f"{resid_pct:+.1f}% ({abs(z):.1f}σ)",
            ),
            ctx.evidence(
                "Explained by index",
                f"{explained_pct:+.1f}% (beta {fit.beta:.2f}, R² {fit.r_squared:.2f})",
            ),
            ctx.evidence(
                "Residual volatility (60d)",
                f"{fit.resid_sd * 100:.2f}% per session",
            ),
        ],
    )
