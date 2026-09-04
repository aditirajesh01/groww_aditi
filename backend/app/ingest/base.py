"""The feed adapter interface.

One interface, three implementations (yahoo, simulator, and the reconciler that
consumes two of them). Everything downstream — adjustment, detection, scoring —
sees only this shape, which is why swapping a real NSE feed in later is a file,
not a refactor.

Every quote carries provenance and an as-of timestamp from the moment it enters
the system. DESIGN.md §8 requires freshness to be *rendered, not hidden*; the
only way to guarantee that is to make it impossible to construct a price in this
codebase without one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Quote:
    symbol: str
    last: float
    prev_close: float
    volume: float
    as_of: datetime
    source: str
    session_index: int = 0

    @property
    def change_abs(self) -> float:
        return self.last - self.prev_close

    @property
    def change_pct(self) -> float:
        if self.prev_close == 0:
            return 0.0
        return (self.last / self.prev_close - 1.0) * 100.0


@dataclass(frozen=True)
class BarPoint:
    symbol: str
    session_index: int
    ts: datetime
    close: float
    volume: float


@dataclass(frozen=True)
class CorpAction:
    """A split / bonus / dividend.

    `known_at_session` may be later than `ex_session`. That gap is the whole
    reason corrections exist, so it is a first-class field rather than an
    exception path.
    """

    symbol: str
    kind: str              # "split" | "bonus" | "dividend"
    ex_session: int
    known_at_session: int
    ratio_from: float = 1.0
    ratio_to: float = 1.0
    cash_amount: float = 0.0
    description: str = ""

    @property
    def price_factor(self) -> float:
        """Multiply a pre-ex-date price by this to put it on the post-action scale.

        1:5 split  -> ratio_from=1, ratio_to=5 -> factor 0.2   (price /5)
        1:3 bonus  -> 3 new for 1 held -> 4 total -> factor 0.25
        dividend   -> handled by the caller against the price level.
        """
        if self.kind == "split":
            return self.ratio_from / self.ratio_to
        if self.kind == "bonus":
            # ratio_to new shares for every ratio_from held.
            return self.ratio_from / (self.ratio_from + self.ratio_to)
        return 1.0


@dataclass(frozen=True)
class MarketEvent:
    """A discrete corporate event with a prior on how much it should matter."""

    symbol: str
    session_index: int
    kind: str            # earnings | guidance | rating | block_deal | pledge | index
    headline: str
    prior: float
    implied_move_pct: float = 0.0
    payload: dict = field(default_factory=dict)


@runtime_checkable
class FeedAdapter(Protocol):
    """What every data source must provide."""

    name: str

    async def quote(self, symbol: str) -> Quote | None:
        """Latest price for one symbol, or None if this source has no opinion."""
        ...

    async def quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Batch form. Sources that support it should override for one round trip."""
        ...

    async def history(self, symbol: str, sessions: int) -> list[BarPoint]:
        """Trailing closes, oldest first. Used to warm the rolling statistics."""
        ...

    async def corporate_actions(self, symbol: str) -> list[CorpAction]:
        ...

    async def corporate_events(self, symbol: str) -> list[MarketEvent]:
        ...
