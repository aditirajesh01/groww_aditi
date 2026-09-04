"""What every detector sees, and the rules every detector obeys.

Each detector is a **pure function** `detect(ctx: SignalContext) -> Signal | None`.
No I/O, no database, no clock reads, no shared state. That buys three things:

*   they are trivially unit-testable from a fabricated context;
*   they can run in any order, or in parallel, per symbol;
*   a reviewer can read one file and know exactly what makes that signal fire.

`Signal` is the Pydantic model straight from contracts/types.ts, so a detector
physically cannot emit a shape the API cannot serialise.

Two invariants hold across all of them:

1.  **Every claim carries evidence.** `Signal.evidence[]` is not decoration —
    contracts/API.md forbids any statement in a summary that is not traceable
    to it, and the summariser is only ever handed evidence rows.
2.  **`detail` is factual, never advisory.** "Down 6.2%, 3.4x average volume" is
    allowed. "Looks oversold" is not. See llm/compliance.py, which enforces this
    on generated text too.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..schemas import Evidence, Signal
from ..universe import SymbolSpec

COMPUTED = "computed"


@dataclass
class SignalContext:
    """Everything a detector is allowed to know about one symbol, right now.

    Built once per symbol per ingest cycle by pipeline.py, from data that has
    *already been corporate-action adjusted*. A detector never sees a raw
    quoted price, which is how the "adjust before detect" rule is enforced
    structurally rather than by remembering to do it.
    """

    symbol: str
    name: str
    spec: SymbolSpec
    session_index: int
    as_of: str

    # Adjusted closes and their returns, oldest first.
    closes: np.ndarray
    returns: np.ndarray

    # The index (NIFTY), same length as `returns`.
    index_returns: np.ndarray
    index_closes: np.ndarray

    volumes: np.ndarray

    # Sector peers: symbol -> aligned return series.
    peer_returns: dict[str, np.ndarray] = field(default_factory=dict)
    sector_returns: np.ndarray | None = None

    # Discrete corporate events keyed by session index.
    events: list = field(default_factory=list)

    # Aggregate, k-anonymised watchlist flow: (session_index, net_adds, cohort).
    flow: list[tuple[int, int, int]] = field(default_factory=list)

    freshness: str = "LIVE"
    change_pct: float = 0.0

    # ---- convenience ----------------------------------------------------

    @property
    def last_return(self) -> float:
        return float(self.returns[-1]) if self.returns.size else 0.0

    @property
    def last_index_return(self) -> float:
        return float(self.index_returns[-1]) if self.index_returns.size else 0.0

    @property
    def enough_history(self) -> bool:
        return self.returns.size >= 40

    def event_at(self, session_index: int):
        for e in self.events:
            if e.session_index == session_index:
                return e
        return None

    def evidence(self, label: str, value: str, source: str = COMPUTED) -> Evidence:
        return Evidence(label=label, value=value, as_of=self.as_of, source=source, url=None)


def direction_of(z: float, flat: float = 0.25) -> str:
    if z > flat:
        return "up"
    if z < -flat:
        return "down"
    return "neutral"


__all__ = ["SignalContext", "Signal", "Evidence", "direction_of", "COMPUTED"]
