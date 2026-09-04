"""Pydantic v2 mirror of contracts/types.ts.

This file is a translation, not an interpretation. Field names, ordering,
optionality and literal unions match the TypeScript one-for-one; the fixtures in
contracts/fixtures/ are the acceptance test (see tests/test_contract_shape.py,
which walks every fixture key against these models).

Rule: nothing here may be changed without changing contracts/types.ts,
contracts/API.md and the fixtures in the same commit.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Freshness = Literal["LIVE", "DELAYED", "STALE", "SUSPECT"]
MarketState = Literal["PRE", "OPEN", "POST", "CLOSED"]
SummaryState = Literal["READY", "PENDING", "UNAVAILABLE"]
Direction = Literal["up", "down", "neutral"]

SignalKind = Literal[
    "IDIOSYNCRATIC_MOVE",
    "DRIFT",
    "REGIME_CHANGE",
    "CORRELATION_BREAK",
    "VOLUME_SURPRISE",
    "CORPORATE_EVENT",
    "ABSENCE",
    "CROWD_FLOW",
    "THESIS_CONTRADICTION",
    "CORRECTION",
]

# Always surfaced regardless of the attention budget (see types.ts).
ALWAYS_SHOWN: frozenset[str] = frozenset({"THESIS_CONTRADICTION", "CORRECTION"})


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Strict):
    label: str
    value: str
    as_of: str
    source: str
    url: str | None = None


class Signal(Strict):
    kind: SignalKind
    z: float
    direction: Direction
    detail: str
    evidence: list[Evidence] = Field(default_factory=list)


class Provenance(Strict):
    source: str
    as_of: str
    freshness: Freshness
    disagreement_pct: float | None = None
    corporate_action_adjusted: bool


class PricePoint(Strict):
    last: float
    change_abs: float
    change_pct: float
    idiosyncratic_pct: float | None = None
    since_last_seen_pct: float | None = None
    vol_z: float
    currency: Literal["INR"] = "INR"


class ThesisImpact(Strict):
    thesis: str
    verdict: Literal["SUPPORTS", "CONTRADICTS", "NEUTRAL"]
    confidence: float
    rationale: str


class ChangeItem(Strict):
    event_id: str
    seq: int
    symbol: str
    name: str
    attention: float
    confirmations: int
    headline: str
    summary: str | None = None
    summary_state: SummaryState
    signals: list[Signal]
    thesis_impact: ThesisImpact | None = None
    price: PricePoint
    provenance: Provenance
    first_seen: str
    is_unread: bool


class QuietItem(Strict):
    symbol: str
    name: str
    reason: str
    change_pct: float
    provenance: Provenance


class AttentionBudget(Strict):
    cap: int
    shown: int
    suppressed: int


class MarketSnapshot(Strict):
    state: MarketState
    nifty_pct: float
    as_of: str


class DigestResponse(Strict):
    generated_at: str
    last_checked_at: str | None = None
    market: MarketSnapshot
    budget: AttentionBudget
    items: list[ChangeItem]
    quiet: list[QuietItem]
    corrections: list[ChangeItem]


class Position(Strict):
    qty: float
    avg_cost: float


class WatchEntry(Strict):
    symbol: str
    name: str
    thesis: str | None = None
    thesis_added_at: str | None = None
    position: Position | None = None
    muted_kinds: list[SignalKind] = Field(default_factory=list)
    added_at: str
    last_seen_seq: int
    price: PricePoint
    provenance: Provenance


class WatchlistResponse(Strict):
    entries: list[WatchEntry]
    unread_total: int


class SymbolRef(Strict):
    symbol: str
    name: str
    exchange: Literal["NSE", "BSE"] = "NSE"


class SparklinePoint(Strict):
    t: str
    c: float


class SymbolDetail(Strict):
    symbol: str
    name: str
    price: PricePoint
    provenance: Provenance
    thesis: str | None = None
    timeline: list[ChangeItem]
    sparkline: list[SparklinePoint]


class ProviderHealth(Strict):
    name: str
    state: Literal["OK", "RATE_LIMITED", "QUOTA_EXHAUSTED", "CIRCUIT_OPEN"]
    used_today: int
    daily_cap: int
    resets_at: str | None = None


class MarketDataHealth(Strict):
    source: str
    freshness: Freshness
    as_of: str


class HealthResponse(Strict):
    ok: bool
    market_data: MarketDataHealth
    llm_providers: list[ProviderHealth]
    cache_hit_rate_24h: float


# --------------------------------------------------------------------------
# Request bodies. Not in types.ts (which only describes responses); shapes are
# taken from the endpoint table in contracts/API.md.
# --------------------------------------------------------------------------


class SessionRequest(Strict):
    device_id: str


class SessionResponse(Strict):
    user_id: str
    token: str


class AddWatchRequest(Strict):
    symbol: str
    thesis: str | None = None
    position: Position | None = None


class PatchWatchRequest(Strict):
    thesis: str | None = None
    position: Position | None = None
    muted: list[SignalKind] | None = None


class AckRequest(Strict):
    event_ids: list[str]


class AckResponse(Strict):
    acked: int
    cursors: dict[str, int]
    unread_total: int


class DismissRequest(Strict):
    event_id: str
    signal_kind: SignalKind


class DismissResponse(Strict):
    ok: bool
    signal_kind: SignalKind
    new_threshold: float


class SimAdvanceRequest(Strict):
    hours: float = 24.0


class SimAdvanceResponse(Strict):
    now: str
    advanced_hours: float
    sessions_generated: int
    events_created: int
    market: MarketSnapshot
