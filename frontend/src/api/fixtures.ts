/**
 * Fixture-backed implementation of ApiClient.
 *
 * It imports contracts/fixtures/*.json directly — the same bytes the backend
 * is being built against — and layers a small stateful simulator on top so the
 * read-cursor semantics are actually exercised, not faked:
 *
 *   - per-user-per-symbol `last_seen_seq`, advanced with max() on ack
 *   - dismissal teaches a per-(symbol, signal_kind) threshold
 *   - /sim/advance releases pre-authored later events, including deliberately
 *     degraded ones (summary UNAVAILABLE, freshness SUSPECT) so the UI's
 *     degradation paths are demonstrable without breaking the backend
 *
 * Everything here is behind VITE_USE_FIXTURES and never ships in live mode.
 */
import digestFixture from "@contracts/fixtures/digest.json";
import watchlistFixture from "@contracts/fixtures/watchlist.json";
import healthFixture from "@contracts/fixtures/health.json";

import type { ApiClient, AddWatchInput, PatchWatchInput } from "./client";
import { ApiError } from "./client";
import type {
  ChangeItem,
  DigestResponse,
  DiscoverCard,
  HealthResponse,
  QuietItem,
  SymbolDetail,
  SymbolRef,
  WatchEntry,
  WatchlistResponse,
} from "./types";

const LATENCY = Number(import.meta.env.VITE_FIXTURE_LATENCY_MS ?? 420);

const clone = <T,>(v: T): T => structuredClone(v);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Simulated round trip, jittered so loading states look real rather than metronomic. */
async function latency(weight = 1) {
  if (LATENCY <= 0) return;
  await sleep(LATENCY * weight * (0.75 + Math.random() * 0.5));
}

// ---------------------------------------------------------------- mutable state

const seed = clone(digestFixture) as unknown as DigestResponse;
const seedWatchlist = clone(watchlistFixture) as unknown as WatchlistResponse;

/** Every change the simulator knows about, in one pool, ranked at read time. */
let pool: ChangeItem[] = [...seed.items];
let corrections: ChangeItem[] = [...seed.corrections];
let quiet: QuietItem[] = [...seed.quiet];
let entries: WatchEntry[] = [...seedWatchlist.entries];

/** Per-user-per-symbol read cursor. Merge across devices is max(). */
const cursor = new Map<string, number>();
/** Items read during this session stay visible until the next fetch cycle. */
let sessionRead = new Set<string>();
/** Dismissals: "SYMBOL:KIND" -> the personal threshold we just learned. */
const dismissed = new Set<string>();
let extraSuppressed = 0;
let simHoursElapsed = 0;

// Seed the cursor from the fixture so the first render reproduces digest.json
// byte-for-byte: unread items sit above the cursor, read ones sit on it.
for (const item of [...seed.items, ...seed.corrections]) {
  const at = item.is_unread ? item.seq - 1 : item.seq;
  cursor.set(item.symbol, Math.max(cursor.get(item.symbol) ?? 0, at));
  if (!item.is_unread) sessionRead.add(item.event_id);
}

const nowIso = () => new Date(Date.parse(seed.generated_at) + simHoursElapsed * 3600_000).toISOString();

// -------------------------------------------------- pre-authored "later" events
// Released by POST /sim/advance. These exist to make the degradation contract
// demonstrable: a card with no LLM summary, and a card whose sources disagree.

function laterEvents(): ChangeItem[] {
  const t = nowIso();
  return [
    {
      event_id: "evt_sim_ETERNAL_1",
      seq: 184260,
      symbol: "ETERNAL",
      name: "Eternal",
      attention: 66,
      confirmations: 2,
      headline: "Sources reconciled — 3.1σ idiosyncratic move confirmed on 2.7x volume",
      summary: null,
      summary_state: "UNAVAILABLE",
      signals: [
        {
          kind: "IDIOSYNCRATIC_MOVE",
          z: -3.1,
          direction: "down",
          detail:
            "Down 4.9% raw; 4.2% is idiosyncratic after stripping Nifty Midcap beta of 1.14.",
          evidence: [
            {
              label: "Beta-adjusted residual",
              value: "-4.2% (3.1σ)",
              as_of: t,
              source: "computed",
              url: null,
            },
          ],
        },
        {
          kind: "VOLUME_SURPRISE",
          z: 2.7,
          direction: "up",
          detail: "2.7x 20-day average volume.",
          evidence: [
            { label: "Volume vs 20d avg", value: "2.7x", as_of: t, source: "computed", url: null },
          ],
        },
      ],
      thesis_impact: {
        thesis: "want it under 240",
        verdict: "SUPPORTS",
        confidence: 0.64,
        rationale:
          "Last traded 246.40, within 2.7% of the level you named. This is dated evidence about your stated condition, not a suggestion.",
      },
      price: {
        last: 246.4,
        change_abs: -12.7,
        change_pct: -4.9,
        idiosyncratic_pct: -4.2,
        since_last_seen_pct: -4.9,
        vol_z: 2.7,
        currency: "INR",
      },
      provenance: {
        source: "nse",
        as_of: t,
        freshness: "DELAYED",
        disagreement_pct: null,
        corporate_action_adjusted: true,
      },
      first_seen: t,
      is_unread: true,
    },
    {
      event_id: "evt_sim_HDFCBANK_2",
      seq: 184255,
      symbol: "HDFCBANK",
      name: "HDFC Bank",
      attention: 52,
      confirmations: 2,
      headline: "Sources disagree by 1.8% — derived signals suppressed until reconciled",
      summary: null,
      summary_state: "PENDING",
      signals: [
        {
          kind: "REGIME_CHANGE",
          z: 2.1,
          direction: "neutral",
          detail:
            "Elevated-vol regime persists into a seventh session. Underlying print is unreliable, so strength is reported but not acted on.",
          evidence: [
            {
              label: "Quote disagreement",
              value: "1.8% between nse and yahoo",
              as_of: t,
              source: "reconciliation",
              url: null,
            },
          ],
        },
        {
          kind: "VOLUME_SURPRISE",
          z: 2.0,
          direction: "up",
          detail: "2.0x 20-day average volume on the unreliable print.",
          evidence: [
            { label: "Volume vs 20d avg", value: "2.0x", as_of: t, source: "computed", url: null },
          ],
        },
      ],
      thesis_impact: null,
      price: {
        last: 1951.05,
        change_abs: 7.25,
        change_pct: 0.37,
        idiosyncratic_pct: null,
        since_last_seen_pct: 0.37,
        vol_z: 2.0,
        currency: "INR",
      },
      provenance: {
        source: "nse+yahoo",
        as_of: t,
        freshness: "SUSPECT",
        disagreement_pct: 1.8,
        corporate_action_adjusted: true,
      },
      first_seen: t,
      is_unread: true,
    },
  ];
}

// ------------------------------------------------------------------ derivations

const isPriority = (item: ChangeItem) =>
  item.signals.some((s) => s.kind === "CORRECTION" || s.kind === "THESIS_CONTRADICTION");

function visible(item: ChangeItem): boolean {
  const seen = cursor.get(item.symbol) ?? 0;
  if (item.seq > seen) return true;
  return sessionRead.has(item.event_id);
}

function suppressedByDismissal(item: ChangeItem): boolean {
  if (isPriority(item)) return false; // never budgeted away, never mutable away
  return item.signals.every((s) => dismissed.has(`${item.symbol}:${s.kind}`));
}

function buildDigest(): DigestResponse {
  const cap = seed.budget.cap;
  const live = pool
    .filter(visible)
    .filter((i) => !suppressedByDismissal(i))
    .map((item) => ({
      ...clone(item),
      is_unread: item.seq > (cursor.get(item.symbol) ?? 0),
    }))
    .sort((a, b) => b.attention - a.attention);

  const shown = live.slice(0, cap);
  const lostTheRanking = Math.max(0, live.length - shown.length);

  return {
    generated_at: nowIso(),
    last_checked_at: seed.last_checked_at,
    market: { ...seed.market, as_of: nowIso() },
    budget: {
      cap,
      shown: shown.length,
      suppressed: seed.budget.suppressed + extraSuppressed + lostTheRanking,
    },
    items: shown,
    quiet: clone(quiet),
    corrections: corrections
      .filter((c) => visible(c) || true) // corrections are never budgeted or cursor-hidden away
      .map((c) => ({ ...clone(c), is_unread: c.seq > (cursor.get(c.symbol) ?? 0) })),
  };
}

// ------------------------------------------------------------ symbol synthesis
// GET /symbols/{symbol} has no fixture. We synthesise it deterministically from
// the digest + watchlist so the detail screen is real data, not lorem ipsum.

function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** mulberry32 — same symbol always yields the same sparkline. */
function rng(seedValue: number) {
  let a = seedValue;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function sparkline(symbol: string, last: number, totalPct: number, points = 60) {
  const rand = rng(hash(symbol));
  const start = last / (1 + totalPct / 100);
  const out: { t: string; c: number }[] = [];
  const dayMs = 86400_000;
  const end = Date.parse(nowIso());
  let level = start;
  const driftPerStep = (last - start) / points;
  for (let i = 0; i < points; i++) {
    const noise = (rand() - 0.5) * start * 0.012;
    level = level + driftPerStep + noise;
    out.push({
      t: new Date(end - (points - 1 - i) * dayMs).toISOString(),
      c: Math.round(level * 100) / 100,
    });
  }
  out[out.length - 1] = { t: nowIso(), c: last };
  return out;
}

const CATALOGUE: SymbolRef[] = [
  { symbol: "TATAMOTORS", name: "Tata Motors", exchange: "NSE", sector: "AUTO" },
  { symbol: "SUNPHARMA", name: "Sun Pharmaceutical", exchange: "NSE", sector: "PHARMA" },
  { symbol: "HDFCBANK", name: "HDFC Bank", exchange: "NSE", sector: "BANK" },
  { symbol: "INFY", name: "Infosys", exchange: "NSE", sector: "IT" },
  { symbol: "TCS", name: "Tata Consultancy Services", exchange: "NSE", sector: "IT" },
  { symbol: "DMART", name: "Avenue Supermarts", exchange: "NSE", sector: "CONSUMER" },
  { symbol: "ETERNAL", name: "Eternal", exchange: "NSE", sector: "CONSUMER" },
  { symbol: "WIPRO", name: "Wipro", exchange: "NSE", sector: "IT" },
  { symbol: "RELIANCE", name: "Reliance Industries", exchange: "NSE", sector: "ENERGY" },
  { symbol: "ICICIBANK", name: "ICICI Bank", exchange: "NSE", sector: "BANK" },
  { symbol: "AXISBANK", name: "Axis Bank", exchange: "NSE", sector: "BANK" },
  { symbol: "KOTAKBANK", name: "Kotak Mahindra Bank", exchange: "NSE", sector: "BANK" },
  { symbol: "LT", name: "Larsen & Toubro", exchange: "NSE", sector: "INFRA" },
  { symbol: "MARUTI", name: "Maruti Suzuki India", exchange: "NSE", sector: "AUTO" },
  { symbol: "BAJFINANCE", name: "Bajaj Finance", exchange: "NSE", sector: "BANK" },
  { symbol: "TITAN", name: "Titan Company", exchange: "NSE", sector: "CONSUMER" },
  { symbol: "ASIANPAINT", name: "Asian Paints", exchange: "NSE", sector: "CONSUMER" },
  { symbol: "HINDUNILVR", name: "Hindustan Unilever", exchange: "NSE", sector: "FMCG" },
  { symbol: "ITC", name: "ITC", exchange: "NSE", sector: "FMCG" },
  { symbol: "ADANIPORTS", name: "Adani Ports & SEZ", exchange: "NSE", sector: "INFRA" },
  { symbol: "POWERGRID", name: "Power Grid Corporation", exchange: "NSE", sector: "INFRA" },
  { symbol: "ZOMATO", name: "Zomato", exchange: "NSE", sector: "CONSUMER" },
  { symbol: "PAYTM", name: "One97 Communications", exchange: "NSE", sector: "IT" },
  { symbol: "IRCTC", name: "Indian Railway Catering & Tourism", exchange: "NSE", sector: "INFRA" },
  { symbol: "TATASTEEL", name: "Tata Steel", exchange: "NSE", sector: "METAL" },
  { symbol: "JSWSTEEL", name: "JSW Steel", exchange: "NSE", sector: "METAL" },
  { symbol: "NESTLEIND", name: "Nestlé India", exchange: "BSE", sector: "FMCG" },
  { symbol: "BRITANNIA", name: "Britannia Industries", exchange: "NSE", sector: "FMCG" },
];

// ------------------------------------------------------------------- the client

export function createFixtureClient(): ApiClient {
  return {
    mode: "fixtures",

    async getDigest() {
      await latency();
      const digest = buildDigest();
      // Anything read in a previous cycle is retired once the next fetch lands,
      // which is what lets the user genuinely reach inbox zero.
      sessionRead = new Set([...sessionRead].filter((id) => digest.items.some((i) => i.event_id === id)));
      return digest;
    },

    async ackDigest(eventIds) {
      await latency(0.4);
      for (const id of eventIds) {
        const item = [...pool, ...corrections].find((i) => i.event_id === id);
        if (!item) continue;
        // max() — acking a stale set can never move the cursor backwards.
        cursor.set(item.symbol, Math.max(cursor.get(item.symbol) ?? 0, item.seq));
        sessionRead.add(item.event_id);
      }
      const list = entries;
      for (const e of list) e.last_seen_seq = Math.max(e.last_seen_seq, cursor.get(e.symbol) ?? 0);
    },

    async dismiss(eventId, signalKind) {
      await latency(0.4);
      const item = pool.find((i) => i.event_id === eventId);
      if (!item) throw new ApiError("unknown event", 404, "/digest/dismiss");
      dismissed.add(`${item.symbol}:${signalKind}`);
      cursor.set(item.symbol, Math.max(cursor.get(item.symbol) ?? 0, item.seq));
      sessionRead.delete(item.event_id);
      extraSuppressed += 1;
      const entry = entries.find((e) => e.symbol === item.symbol);
      if (entry && !entry.muted_kinds.includes(signalKind)) entry.muted_kinds.push(signalKind);
    },

    async getWatchlist() {
      await latency(0.7);
      return {
        entries: clone(entries),
        unread_total: pool
          .filter(visible)
          .filter((i) => i.seq > (cursor.get(i.symbol) ?? 0)).length,
      };
    },

    async addWatch(input: AddWatchInput) {
      await latency(0.6);
      const sym = input.symbol.toUpperCase();
      if (entries.some((e) => e.symbol === sym))
        throw new ApiError(`${sym} is already on your watchlist`, 409, "/watchlist");
      const ref = CATALOGUE.find((c) => c.symbol === sym);
      const rand = rng(hash(sym));
      const last = Math.round((200 + rand() * 2400) * 100) / 100;
      const pct = Math.round((rand() * 4 - 2) * 100) / 100;
      const entry: WatchEntry = {
        symbol: sym,
        name: ref?.name ?? sym,
        thesis: input.thesis?.trim() ? input.thesis.trim() : null,
        thesis_added_at: input.thesis?.trim() ? nowIso() : null,
        position: input.position ?? null,
        muted_kinds: [],
        added_at: nowIso(),
        last_seen_seq: 184213,
        price: {
          last,
          change_abs: Math.round(last * (pct / 100) * 100) / 100,
          change_pct: pct,
          idiosyncratic_pct: Math.round(pct * 0.6 * 100) / 100,
          since_last_seen_pct: null,
          vol_z: Math.round((rand() * 2 - 0.5) * 10) / 10,
          currency: "INR",
        },
        provenance: {
          source: "nse",
          as_of: nowIso(),
          freshness: "LIVE",
          disagreement_pct: null,
          corporate_action_adjusted: true,
        },
      };
      entries = [entry, ...entries];
      quiet = [
        {
          symbol: sym,
          name: entry.name,
          reason: "just added — no baseline yet, first signal after 20 sessions of history",
          change_pct: pct,
          provenance: clone(entry.provenance),
        },
        ...quiet,
      ];
      return clone(entry);
    },

    async patchWatch(symbol, patch: PatchWatchInput) {
      await latency(0.5);
      const entry = entries.find((e) => e.symbol === symbol.toUpperCase());
      if (!entry) throw new ApiError("not on your watchlist", 404, `/watchlist/${symbol}`);
      if (patch.thesis !== undefined) {
        const next = patch.thesis?.trim() ?? "";
        const changed = next !== (entry.thesis ?? "");
        entry.thesis = next ? next : null;
        if (changed) entry.thesis_added_at = next ? nowIso() : null;
      }
      if (patch.position !== undefined) entry.position = patch.position;
      if (patch.muted !== undefined) entry.muted_kinds = patch.muted;
      return clone(entry);
    },

    async removeWatch(symbol) {
      await latency(0.5);
      const sym = symbol.toUpperCase();
      entries = entries.filter((e) => e.symbol !== sym);
      pool = pool.filter((i) => i.symbol !== sym);
      quiet = quiet.filter((q) => q.symbol !== sym);
      corrections = corrections.filter((c) => c.symbol !== sym);
    },

    async getSymbol(symbol) {
      await latency();
      const sym = symbol.toUpperCase();
      const entry = entries.find((e) => e.symbol === sym);
      const timeline = [...pool, ...corrections]
        .filter((i) => i.symbol === sym)
        .map((i) => ({ ...clone(i), is_unread: i.seq > (cursor.get(i.symbol) ?? 0) }))
        .sort((a, b) => b.seq - a.seq);
      const quietRow = quiet.find((q) => q.symbol === sym);
      const ref = CATALOGUE.find((c) => c.symbol === sym);

      if (!entry && timeline.length === 0 && !ref)
        throw new ApiError("unknown symbol", 404, `/symbols/${symbol}`);

      const price =
        entry?.price ??
        timeline[0]?.price ?? {
          last: 100,
          change_abs: 0,
          change_pct: quietRow?.change_pct ?? 0,
          idiosyncratic_pct: null,
          since_last_seen_pct: null,
          vol_z: 0,
          currency: "INR" as const,
        };
      const provenance =
        entry?.provenance ??
        timeline[0]?.provenance ??
        quietRow?.provenance ?? {
          source: "sim",
          as_of: nowIso(),
          freshness: "DELAYED" as const,
          disagreement_pct: null,
          corporate_action_adjusted: true,
        };

      return {
        symbol: sym,
        name: entry?.name ?? timeline[0]?.name ?? ref?.name ?? sym,
        price: clone(price),
        provenance: clone(provenance),
        thesis: entry?.thesis ?? null,
        timeline,
        sparkline: sparkline(sym, price.last, (price.since_last_seen_pct ?? price.change_pct) * 3),
      } satisfies SymbolDetail;
    },

    async search(q) {
      await latency(0.25);
      const needle = q.trim().toUpperCase();
      if (!needle) return [];
      return CATALOGUE.filter(
        (c) => c.symbol.includes(needle) || c.name.toUpperCase().includes(needle),
      ).slice(0, 8);
    },

    async discover() {
      await latency(0.6);
      const watchedSymbols = new Set(entries.map((e) => e.symbol));
      const sectorCounts = new Map<string, number>();
      for (const e of entries) {
        const ref = CATALOGUE.find((c) => c.symbol === e.symbol);
        if (ref) sectorCounts.set(ref.sector, (sectorCounts.get(ref.sector) ?? 0) + 1);
      }
      const totalWatched = entries.length || 1;

      const cards: DiscoverCard[] = CATALOGUE.filter((c) => !watchedSymbols.has(c.symbol)).map(
        (c) => {
          const rand = rng(hash(c.symbol));
          const last = Math.round((200 + rand() * 2400) * 100) / 100;
          const pct = Math.round((rand() * 4 - 2) * 100) / 100;
          const shared = sectorCounts.get(c.sector) ?? 0;
          return {
            symbol: c.symbol,
            name: c.name,
            sector: c.sector,
            price: {
              last,
              change_abs: Math.round(last * (pct / 100) * 100) / 100,
              change_pct: pct,
              idiosyncratic_pct: Math.round(pct * 0.6 * 100) / 100,
              since_last_seen_pct: null,
              vol_z: Math.round((rand() * 2 - 0.5) * 10) / 10,
              currency: "INR",
            },
            provenance: {
              source: "sim",
              as_of: nowIso(),
              freshness: "LIVE",
              disagreement_pct: null,
              corporate_action_adjusted: true,
            },
            match: { shared, total: totalWatched, ratio: Math.round((shared / totalWatched) * 100) / 100 },
          };
        },
      );

      cards.sort((a, b) => b.match.ratio - a.match.ratio);
      return cards.slice(0, 15);
    },

    async getHealth() {
      await latency(0.3);
      return clone(healthFixture) as unknown as HealthResponse;
    },

    async advanceSim(hours) {
      await latency(0.8);
      simHoursElapsed += hours;
      sessionRead = new Set();
      for (const ev of laterEvents()) {
        if (!pool.some((p) => p.event_id === ev.event_id)) pool.push(ev);
      }
      quiet = quiet.filter((q) => !pool.some((p) => p.symbol === q.symbol && visible(p)));
    },
  };
}
