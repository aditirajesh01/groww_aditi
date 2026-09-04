import { ApiError } from "./client";
import type {
  ApiClient,
  AddWatchInput,
  PatchWatchInput,
} from "./client";
import type {
  DigestResponse,
  DiscoverCard,
  HealthResponse,
  SignalKind,
  SymbolDetail,
  SymbolRef,
  WatchEntry,
  WatchlistResponse,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "/api/v1").replace(/\/$/, "");
const TOKEN_KEY = "smw.token";
const DEVICE_KEY = "smw.device_id";

function deviceId(): string {
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

/** POST /auth/session {device_id} -> {user_id, token}. Same device_id, same user. */
async function ensureToken(): Promise<string> {
  const existing = localStorage.getItem(TOKEN_KEY);
  if (existing) return existing;
  const res = await fetch(`${BASE}/auth/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ device_id: deviceId() }),
  });
  if (!res.ok) throw new ApiError("could not open a session", res.status, "/auth/session");
  const json = (await res.json()) as { user_id: string; token: string };
  localStorage.setItem(TOKEN_KEY, json.token);
  return json.token;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await ensureToken();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    throw new ApiError("session expired", 401, path);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? body?.message ?? detail;
    } catch {
      /* body was not JSON; the status line is all we have */
    }
    throw new ApiError(detail, res.status, path);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function createHttpClient(): ApiClient {
  return {
    mode: "live",
    getDigest: () => request<DigestResponse>("/digest"),
    ackDigest: (event_ids: string[]) =>
      request<void>("/digest/ack", { method: "POST", body: JSON.stringify({ event_ids }) }),
    dismiss: (event_id: string, signal_kind: SignalKind) =>
      request<void>("/digest/dismiss", {
        method: "POST",
        body: JSON.stringify({ event_id, signal_kind }),
      }),
    getWatchlist: () => request<WatchlistResponse>("/watchlist"),
    addWatch: (input: AddWatchInput) =>
      request<WatchEntry>("/watchlist", { method: "POST", body: JSON.stringify(input) }),
    patchWatch: (symbol: string, patch: PatchWatchInput) =>
      request<WatchEntry>(`/watchlist/${encodeURIComponent(symbol)}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      }),
    removeWatch: (symbol: string) =>
      request<void>(`/watchlist/${encodeURIComponent(symbol)}`, { method: "DELETE" }),
    getSymbol: (symbol: string) =>
      request<SymbolDetail>(`/symbols/${encodeURIComponent(symbol)}`),
    search: (q: string) => request<SymbolRef[]>(`/search?q=${encodeURIComponent(q)}`),
    discover: () => request<DiscoverCard[]>("/discover"),
    getHealth: () => request<HealthResponse>("/health"),
    advanceSim: (hours: number) =>
      request<void>("/sim/advance", { method: "POST", body: JSON.stringify({ hours }) }),
  };
}
