"""Personal materiality — the same 4% move is front-page for one user and noise
for another.

DESIGN.md §2(1). This is stage two of the gate and the reason the read path is
`fan-out on read`: it is pure arithmetic over precomputed vectors, roughly ten
float operations per symbol, so recomputing it per user per request costs less
than storing it would.

Four inputs, each with a defensible reason to be there:

*   **position size** — a 6% move on 40 shares and on 4,000 shares are different
    events. Log-scaled against the user's own book, because materiality is
    relative to what *they* hold, not to a rupee threshold.
*   **proximity to cost basis** — a stock sitting near what you paid is a
    decision zone. Far above or far below, the next 4% changes little about
    what you are going to do; at breakeven it changes everything.
*   **tenure on the list** — something watched for eight months has survived
    eight months of the user deciding not to remove it. That is a revealed
    preference and it is stronger than anything they typed.
*   **open frequency** — how often they actually look. Cheap, honest,
    behavioural.

Deliberately absent: anything about whether the move is *good* for the user.
Weighting a fall more heavily for a holder than for a watcher would be the first
step toward a recommendation engine, which DESIGN.md §9 rules out permanently.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

# Weights sum to 1.0. Position dominates because it is the only input that is
# unambiguously about consequence rather than about interest.
W_POSITION = 0.40
W_BASIS = 0.25
W_TENURE = 0.15
W_OPENS = 0.20

# Nothing on a user's watchlist is irrelevant — they put it there. The floor
# stops a watched-but-unowned symbol from being scored into invisibility.
FLOOR = 0.28


@dataclass(frozen=True)
class UserSymbolProfile:
    symbol: str
    qty: float | None
    avg_cost: float | None
    added_at: datetime
    open_count: int
    has_thesis: bool


def position_weight(qty: float | None, price: float, book_value: float) -> float:
    """Position value as a share of the user's book, log-compressed.

    Linear share would make a single dominant holding score ~1.0 and everything
    else ~0.0. Log compression keeps the ordering while leaving the rest of the
    watchlist legible.
    """
    if not qty or qty <= 0 or price <= 0:
        return 0.0
    value = qty * price
    if book_value <= 0:
        return 0.5
    share = min(1.0, value / book_value)
    return float(math.log1p(9.0 * share) / math.log(10.0))


def basis_proximity(price: float, avg_cost: float | None) -> float:
    """1.0 at breakeven, decaying as the price moves away from cost.

    Half-life of about 12% — beyond roughly a quarter off cost, another few
    percent genuinely does not change the decision the user is facing.
    """
    if not avg_cost or avg_cost <= 0 or price <= 0:
        return 0.0
    gap = abs(price / avg_cost - 1.0)
    return float(math.exp(-gap / 0.12))


def tenure_weight(added_at: datetime, now: datetime) -> float:
    """Saturating in ~6 months. Long tenure is a revealed preference."""
    days = max(0.0, (now - added_at).total_seconds() / 86400.0)
    return float(1.0 - math.exp(-days / 180.0))


def open_weight(open_count: int) -> float:
    """Saturating in ~20 opens, so a power-user's habits do not swamp the term."""
    return float(1.0 - math.exp(-open_count / 20.0))


def relevance(
    profile: UserSymbolProfile,
    price: float,
    book_value: float,
    now: datetime,
) -> float:
    """0..1. Never zero for a watched symbol."""
    score = (
        W_POSITION * position_weight(profile.qty, price, book_value)
        + W_BASIS * basis_proximity(price, profile.avg_cost)
        + W_TENURE * tenure_weight(profile.added_at, now)
        + W_OPENS * open_weight(profile.open_count)
    )
    # A stated thesis is an explicit declaration of interest. Modest bump —
    # it should not out-rank owning the thing.
    if profile.has_thesis:
        score += 0.08
    return float(min(1.0, max(FLOOR, score)))


def explain(
    profile: UserSymbolProfile, price: float, book_value: float, now: datetime
) -> dict[str, float]:
    """Component breakdown. Used by tests and by /symbols/{symbol} debugging;
    never shown to a user as advice."""
    return {
        "position": round(position_weight(profile.qty, price, book_value), 3),
        "basis_proximity": round(basis_proximity(price, profile.avg_cost), 3),
        "tenure": round(tenure_weight(profile.added_at, now), 3),
        "opens": round(open_weight(profile.open_count), 3),
        "relevance": round(relevance(profile, price, book_value, now), 3),
    }
