// Shared types — authoritative alongside contracts/API.md.
// Backend mirrors these as Pydantic models. Do not diverge.

export type Freshness = "LIVE" | "DELAYED" | "STALE" | "SUSPECT";
export type MarketState = "PRE" | "OPEN" | "POST" | "CLOSED";
export type SummaryState = "READY" | "PENDING" | "UNAVAILABLE";
export type Direction = "up" | "down" | "neutral";

/** Every signal type the engine can emit. `THESIS_CONTRADICTION` and
 *  `CORRECTION` are always shown regardless of attention budget. */
export type SignalKind =
  | "IDIOSYNCRATIC_MOVE"   // beta-stripped residual return, in sigma
  | "DRIFT"                // slow cumulative move no threshold alert catches
  | "REGIME_CHANGE"        // BOCPD/CUSUM on realised vol
  | "CORRELATION_BREAK"    // pair/sector divergence
  | "VOLUME_SURPRISE"      // participation confirmation
  | "CORPORATE_EVENT"      // earnings, guidance, rating, block deal, pledge
  | "ABSENCE"              // expected to move, didn't
  | "CROWD_FLOW"           // aggregate k-anonymised watchlist adds/removes
  | "THESIS_CONTRADICTION" // evidence against the user's own stated reason
  | "CORRECTION";          // a previously shown number was revised

export interface Evidence {
  label: string;          // "Q2 gross margin"
  value: string;          // "18.4% (-180bps QoQ)"
  as_of: string;
  source: string;
  url?: string | null;
}

export interface Signal {
  kind: SignalKind;
  z: number;              // strength in sigma; sign carries direction
  direction: Direction;
  detail: string;         // factual, human-readable, never advisory
  evidence: Evidence[];
}

export interface Provenance {
  source: string;                    // "yahoo" | "nse" | "sim"
  as_of: string;
  freshness: Freshness;
  disagreement_pct?: number | null;  // set when freshness === "SUSPECT"
  corporate_action_adjusted: boolean;
}

export interface PricePoint {
  last: number;
  change_abs: number;
  change_pct: number;                 // today, raw
  idiosyncratic_pct: number | null;   // beta-stripped — the part that is news
  since_last_seen_pct: number | null; // the real "since you last checked" delta
  vol_z: number;
  currency: "INR";
}

export interface ThesisImpact {
  thesis: string;                              // the user's own words
  verdict: "SUPPORTS" | "CONTRADICTS" | "NEUTRAL";
  confidence: number;                          // 0..1
  rationale: string;                           // must cite evidence
}

export interface ChangeItem {
  event_id: string;
  seq: number;                 // globally monotonic — drives the read cursor
  symbol: string;
  name: string;
  attention: number;           // 0..100, personal
  confirmations: number;       // >= 2 to be promoted (the two-factor rule)
  headline: string;            // deterministic, never LLM-dependent
  summary: string | null;      // LLM; null unless summary_state === "READY"
  summary_state: SummaryState;
  signals: Signal[];
  thesis_impact: ThesisImpact | null;
  price: PricePoint;
  provenance: Provenance;
  first_seen: string;
  is_unread: boolean;
}

/** A symbol that was checked and had nothing meaningful. Rendering these is
 *  what makes the absence of news trustworthy rather than ambiguous. */
export interface QuietItem {
  symbol: string;
  name: string;
  reason: string;              // "moved 0.4σ, no volume confirmation"
  change_pct: number;
  provenance: Provenance;
}

export interface AttentionBudget {
  cap: number;
  shown: number;
  suppressed: number;          // passed the gate but lost the ranking
}

export interface DigestResponse {
  generated_at: string;
  last_checked_at: string | null;
  market: { state: MarketState; nifty_pct: number; as_of: string };
  budget: AttentionBudget;
  items: ChangeItem[];         // ranked desc by attention, length <= budget.cap
  quiet: QuietItem[];
  corrections: ChangeItem[];   // always surfaced, never budgeted away
}

export interface WatchEntry {
  symbol: string;
  name: string;
  thesis: string | null;
  thesis_added_at: string | null;
  position: { qty: number; avg_cost: number } | null;
  muted_kinds: SignalKind[];
  added_at: string;
  last_seen_seq: number;
  price: PricePoint;
  provenance: Provenance;
}

export interface WatchlistResponse {
  entries: WatchEntry[];
  unread_total: number;
}

export interface SymbolRef { symbol: string; name: string; exchange: "NSE" | "BSE"; sector: string; }

/** Deliberately simple: shared-sector count over total watched -- a ratio,
 *  not a model, so the reasoning behind a Discover ranking fits on the card. */
export interface MatchRatio { shared: number; total: number; ratio: number; }

export interface DiscoverCard {
  symbol: string;
  name: string;
  sector: string;
  price: PricePoint;
  provenance: Provenance;
  match: MatchRatio;
}

export interface SymbolDetail {
  symbol: string;
  name: string;
  price: PricePoint;
  provenance: Provenance;
  thesis: string | null;
  timeline: ChangeItem[];      // full history, newest first
  sparkline: { t: string; c: number }[];
}

/** GET /health — surfaces the LLM rate-limit state so degradation is visible. */
export interface HealthResponse {
  ok: boolean;
  market_data: { source: string; freshness: Freshness; as_of: string };
  llm_providers: {
    name: string;                       // "gemini" | "openrouter" | "template"
    state: "OK" | "RATE_LIMITED" | "QUOTA_EXHAUSTED" | "CIRCUIT_OPEN";
    used_today: number;
    daily_cap: number;
    resets_at: string | null;
  }[];
  cache_hit_rate_24h: number;
}
