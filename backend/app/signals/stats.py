"""The statistics, implemented rather than imported.

All of this is a few dozen lines against numpy. Pulling in scipy/statsmodels to
get `OLS` and `t.logpdf` would add a heavyweight dependency, a wheel-availability
risk on new CPython, and — worse — would hide the two formulas a reviewer
actually wants to check: how beta is estimated, and what the changepoint
posterior really is.

Everything here is a pure function over numpy arrays. No state, no I/O.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

TRADING_DAYS = 252.0


def pct_returns(closes: np.ndarray) -> np.ndarray:
    """Simple session-over-session returns as decimals."""
    closes = np.asarray(closes, dtype=float)
    if closes.size < 2:
        return np.zeros(0)
    return closes[1:] / closes[:-1] - 1.0


def realised_vol(returns: np.ndarray, window: int = 20) -> float:
    """Annualised realised volatility over the trailing `window` returns."""
    r = np.asarray(returns, dtype=float)[-window:]
    if r.size < 2:
        return 0.0
    return float(np.std(r, ddof=1) * math.sqrt(TRADING_DAYS))


def zscore(value: float, sample: np.ndarray) -> float:
    """How many sigma `value` sits from the sample mean."""
    s = np.asarray(sample, dtype=float)
    if s.size < 3:
        return 0.0
    sd = float(np.std(s, ddof=1))
    if sd < 1e-12:
        return 0.0
    return float((value - float(np.mean(s))) / sd)


@dataclass(frozen=True)
class OLSFit:
    """A rolling market-model fit:  r_stock = alpha + beta * r_index + e."""

    alpha: float
    beta: float
    resid_sd: float
    r_squared: float
    n: int

    def residual(self, r_stock: float, r_index: float) -> float:
        """The part of today's move that the index does not explain."""
        return r_stock - (self.alpha + self.beta * r_index)

    def residual_z(self, r_stock: float, r_index: float) -> float:
        if self.resid_sd < 1e-12:
            return 0.0
        return self.residual(r_stock, r_index) / self.resid_sd


def rolling_ols(
    stock_returns: np.ndarray, index_returns: np.ndarray, window: int = 60
) -> OLSFit:
    """Ordinary least squares of stock on index over the trailing window.

    Closed form, because with one regressor there is no reason not to:

        beta  = cov(y, x) / var(x)
        alpha = mean(y) - beta * mean(x)

    `resid_sd` is the denominator that turns a rupee move into a sigma. It is
    computed from the residuals, not from the raw return series, which is the
    whole point: a stock that habitually swings 3% with the index is not
    surprising when it swings 3% with the index.
    """
    y = np.asarray(stock_returns, dtype=float)[-window:]
    x = np.asarray(index_returns, dtype=float)[-window:]
    n = min(y.size, x.size)
    if n < 20:
        return OLSFit(alpha=0.0, beta=1.0, resid_sd=float(np.std(y) or 1e-9),
                      r_squared=0.0, n=n)

    y, x = y[-n:], x[-n:]
    x_mean, y_mean = float(np.mean(x)), float(np.mean(y))
    var_x = float(np.var(x, ddof=1))
    if var_x < 1e-16:
        return OLSFit(0.0, 1.0, float(np.std(y, ddof=1)), 0.0, n)

    beta = float(np.cov(y, x, ddof=1)[0, 1] / var_x)
    alpha = y_mean - beta * x_mean
    resid = y - (alpha + beta * x)
    resid_sd = float(np.std(resid, ddof=1))
    var_y = float(np.var(y, ddof=1))
    r_squared = 0.0 if var_y < 1e-16 else max(0.0, 1.0 - float(np.var(resid, ddof=1)) / var_y)

    return OLSFit(alpha=alpha, beta=beta, resid_sd=max(resid_sd, 1e-9),
                  r_squared=r_squared, n=n)


def correlation(a: np.ndarray, b: np.ndarray, window: int | None = None) -> float:
    """Pearson correlation over the trailing `window` observations."""
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    n = min(x.size, y.size)
    if window:
        n = min(n, window)
    if n < 5:
        return 0.0
    x, y = x[-n:], y[-n:]
    sx, sy = float(np.std(x, ddof=1)), float(np.std(y, ddof=1))
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    return float(np.clip(np.cov(x, y, ddof=1)[0, 1] / (sx * sy), -1.0, 1.0))


def fisher_z(rho: float) -> float:
    """Fisher transform. Correlations are bounded and skewed; their z-scores are
    meaningless until you unbound them, so a correlation *break* has to be
    measured in Fisher space or it will over-flag near +/-1."""
    rho = float(np.clip(rho, -0.9999, 0.9999))
    return 0.5 * math.log((1.0 + rho) / (1.0 - rho))


# ---------------------------------------------------------------------------
# Bayesian Online Changepoint Detection  (Adams & MacKay 2007)
#
# DESIGN.md §1 cites BOCPD over GLR/KS on the strength of ~30% fewer false
# alarms on financial series. The reason it does better here is that it does not
# ask "is today unusual"; it maintains a posterior over *how long the current
# regime has been running* and lets that distribution collapse when the
# generating process actually changes.
#
# Observation model: Gaussian with unknown mean AND unknown variance, so the
# conjugate prior is Normal-Gamma and the posterior predictive is Student-t.
# Unknown variance matters — we run this on log realised volatility, where
# assuming a known variance would make every vol cluster look like a regime
# change.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangepointResult:
    probability: float        # posterior mass on "a changepoint happened recently"
    index: int | None         # most likely changepoint position in the input
    run_length: int           # MAP run length at the final observation
    before: float             # mean of the observable before the break
    after: float              # mean after


def _student_t_logpdf(x: float, mu: float, kappa: float, alpha: float, beta: float) -> float:
    """Log posterior predictive of a Normal-Gamma, i.e. a Student-t with
    2*alpha degrees of freedom, location mu and scale^2 = beta(kappa+1)/(alpha*kappa)."""
    nu = 2.0 * alpha
    scale_sq = beta * (kappa + 1.0) / (alpha * kappa)
    scale_sq = max(scale_sq, 1e-12)
    return (
        math.lgamma((nu + 1.0) / 2.0)
        - math.lgamma(nu / 2.0)
        - 0.5 * math.log(nu * math.pi * scale_sq)
        - ((nu + 1.0) / 2.0) * math.log1p((x - mu) ** 2 / (nu * scale_sq))
    )


def bocpd(
    data: np.ndarray,
    hazard: float = 1.0 / 250.0,
    mu0: float = 0.0,
    kappa0: float = 1.0,
    alpha0: float = 1.0,
    beta0: float = 1.0,
    recent_window: int = 12,
) -> ChangepointResult:
    """Run BOCPD and report the posterior probability of a recent changepoint.

    `hazard` is the constant prior probability that any given step starts a new
    regime — 1/250 says "about one regime change per trading year", which is the
    right order of magnitude for realised vol on a large-cap and is what
    DESIGN.md specifies.

    We report `P(run length < recent_window)` at the final step rather than the
    raw `R[0]`. R[0] alone is the probability that the changepoint is *exactly
    now*, which is almost always small and would make the detector look broken;
    the mass on short run lengths is the quantity a human means by "the regime
    changed recently".
    """
    x = np.asarray(data, dtype=float)
    n = x.size
    if n < 20:
        return ChangepointResult(0.0, None, n, 0.0, 0.0)

    # R[r] = P(run length = r | data so far). Starts certain that r = 0.
    R = np.zeros(n + 1)
    R[0] = 1.0

    mu = np.array([mu0], dtype=float)
    kappa = np.array([kappa0], dtype=float)
    alpha = np.array([alpha0], dtype=float)
    beta = np.array([beta0], dtype=float)

    cp_mass = np.zeros(n)  # posterior mass on "a changepoint occurred at t"

    for t in range(n):
        obs = float(x[t])
        active = t + 1

        pred = np.empty(active)
        for r in range(active):
            pred[r] = _student_t_logpdf(obs, mu[r], kappa[r], alpha[r], beta[r])
        pred = np.exp(pred - pred.max())  # stabilised; normalisation cancels

        current = R[:active]
        growth = current * pred * (1.0 - hazard)   # run continues
        cp = float(np.sum(current * pred * hazard))  # run resets

        new_R = np.zeros(n + 1)
        new_R[1 : active + 1] = growth
        new_R[0] = cp
        total = new_R.sum()
        if total <= 0 or not np.isfinite(total):
            break
        R = new_R / total
        cp_mass[t] = R[0]

        # Normal-Gamma update, prepending the fresh prior for the reset branch.
        mu_new = np.concatenate(([mu0], (kappa * mu + obs) / (kappa + 1.0)))
        kappa_new = np.concatenate(([kappa0], kappa + 1.0))
        alpha_new = np.concatenate(([alpha0], alpha + 0.5))
        beta_new = np.concatenate(
            ([beta0], beta + (kappa * (obs - mu) ** 2) / (2.0 * (kappa + 1.0)))
        )
        mu, kappa, alpha, beta = mu_new, kappa_new, alpha_new, beta_new

    window = min(recent_window, n)
    probability = float(np.sum(R[:window]))

    # Most likely break: the recent step carrying the most reset mass.
    tail_from = max(0, n - max(recent_window * 3, 30))
    tail = cp_mass[tail_from:]
    idx: int | None = int(tail_from + int(np.argmax(tail))) if tail.size else None
    if idx is not None and cp_mass[idx] < 1e-6:
        idx = None

    run_length = int(np.argmax(R))
    before = float(np.mean(x[:idx])) if idx and idx >= 3 else float(np.mean(x[: n // 2]))
    after = float(np.mean(x[idx:])) if idx is not None and idx < n else float(np.mean(x[n // 2 :]))

    return ChangepointResult(
        probability=float(np.clip(probability, 0.0, 1.0)),
        index=idx,
        run_length=run_length,
        before=before,
        after=after,
    )


def cusum(data: np.ndarray, threshold: float = 5.0, drift: float = 0.5) -> int | None:
    """Two-sided CUSUM, kept as a cheap sanity check on BOCPD.

    Not used in the request path. It exists so that if BOCPD's posterior ever
    looks implausible on a series, there is a second, boringly simple opinion to
    compare against: accumulate standardised deviations from the running mean
    and flag when the running sum exceeds `threshold` sigma.
    """
    x = np.asarray(data, dtype=float)
    if x.size < 20:
        return None
    mean = float(np.mean(x[: x.size // 2]))
    sd = float(np.std(x[: x.size // 2], ddof=1)) or 1e-9
    g_pos = g_neg = 0.0
    for i, value in enumerate(x):
        s = (value - mean) / sd
        g_pos = max(0.0, g_pos + s - drift)
        g_neg = min(0.0, g_neg + s + drift)
        if g_pos > threshold or g_neg < -threshold:
            return i
    return None
