/**
 * Single source of truth. These types live in ../../contracts/types.ts and are
 * mirrored by the backend as Pydantic models. We re-export rather than redefine
 * so there is exactly one place a shape can change.
 */
export type {
  Freshness,
  MarketState,
  SummaryState,
  Direction,
  SignalKind,
  Evidence,
  Signal,
  Provenance,
  PricePoint,
  ThesisImpact,
  ChangeItem,
  QuietItem,
  AttentionBudget,
  DigestResponse,
  WatchEntry,
  WatchlistResponse,
  SymbolRef,
  SymbolDetail,
  HealthResponse,
  MatchRatio,
  DiscoverCard,
} from "@contracts/types";
