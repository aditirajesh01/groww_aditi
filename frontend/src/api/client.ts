import type {
  DigestResponse,
  HealthResponse,
  SignalKind,
  SymbolDetail,
  SymbolRef,
  WatchEntry,
  WatchlistResponse,
} from "./types";

export interface WatchPosition {
  qty: number;
  avg_cost: number;
}

export interface AddWatchInput {
  symbol: string;
  thesis?: string | null;
  position?: WatchPosition | null;
}

export interface PatchWatchInput {
  thesis?: string | null;
  position?: WatchPosition | null;
  muted?: SignalKind[];
}

/**
 * The contract the UI codes against. Both implementations below satisfy it
 * identically, so swapping fixture mode for the live API is a one-line change
 * in an .env file and nothing in the component tree knows the difference.
 */
export interface ApiClient {
  readonly mode: "fixtures" | "live";
  getDigest(): Promise<DigestResponse>;
  ackDigest(eventIds: string[]): Promise<void>;
  dismiss(eventId: string, signalKind: SignalKind): Promise<void>;
  getWatchlist(): Promise<WatchlistResponse>;
  addWatch(input: AddWatchInput): Promise<WatchEntry>;
  patchWatch(symbol: string, patch: PatchWatchInput): Promise<WatchEntry>;
  removeWatch(symbol: string): Promise<void>;
  getSymbol(symbol: string): Promise<SymbolDetail>;
  search(q: string): Promise<SymbolRef[]>;
  getHealth(): Promise<HealthResponse>;
  advanceSim(hours: number): Promise<void>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly path: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const USE_FIXTURES = import.meta.env.VITE_USE_FIXTURES !== "false";

let cached: ApiClient | null = null;

/** Lazily resolved so the fixture JSON never enters the live-mode bundle. */
export async function getClient(): Promise<ApiClient> {
  if (cached) return cached;
  cached = USE_FIXTURES
    ? (await import("./fixtures")).createFixtureClient()
    : (await import("./http")).createHttpClient();
  return cached;
}

export const API_MODE: "fixtures" | "live" = USE_FIXTURES ? "fixtures" : "live";
