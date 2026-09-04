# Smart Market Watchlist — frontend

> The watchlist is not a dashboard. It is a **changelog with a read cursor**.

React 19 + TypeScript + Vite. [Oat](https://oat.ink) (`@knadh/oat`, ~6KB CSS) as
the base design layer; [Motion](https://motion.dev) for animation. No other
runtime dependencies, no CSS framework, no component library, no webfonts.

---

## Run it

From `frontend/`:

```bash
npm install
npm run dev        # http://localhost:5173
```

That is the whole setup. **No backend is required** — the app defaults to
fixture mode and imports `contracts/fixtures/*.json` directly.

```bash
npm run build      # typecheck (tsc -b) + production build to dist/
npm run preview    # serve the production build
npx tsc -b         # typecheck only
```

### Switching to the live API

One line in `.env` (copy from `.env.example`):

```ini
VITE_USE_FIXTURES=false
VITE_API_BASE=/api/v1          # proxied to http://localhost:8000 by vite.config.ts
```

`src/api/client.ts` declares one `ApiClient` interface. `src/api/fixtures.ts`
and `src/api/http.ts` both implement it and are code-split, so fixture JSON
never enters the live bundle. Nothing in the component tree knows which one it
is talking to.

| Variable | Default | Meaning |
|---|---|---|
| `VITE_USE_FIXTURES` | `true` | `false` sends every call to the real API |
| `VITE_API_BASE` | `/api/v1` | Base path in live mode |
| `VITE_FIXTURE_LATENCY_MS` | `420` | Simulated round trip; `0` for instant |

---

## Where things are

```
src/
  api/        client.ts (the interface) · fixtures.ts · http.ts · types.ts (re-export only)
  state/      store.tsx (digest + cursor + optimistic mutations) · router.ts · theme.ts
  lib/        format.ts · signals.ts · motion.ts (all timings and curves)
  components/ ChangeCard · ThesisConfrontation · Evidence · AttentionMeter ·
              FreshnessChip · Ticker · QuietList · InboxZero · ThesisComposer ·
              Sparkline · Toasts · Skeleton · DigestHeader
  screens/    DigestScreen · WatchlistScreen · SymbolScreen · SystemScreen
  styles/     theme.css (tokens over Oat) · app.css
```

**Types are never redefined.** `src/api/types.ts` re-exports
`contracts/types.ts` verbatim through the `@contracts` alias in
`vite.config.ts` / `tsconfig.app.json`. If the contract changes, this app fails
to compile — which is the point.

---

## Screens

- `#/` — **the digest.** Corrections first, then the ranked change cards (never
  more than `budget.cap`), then the quiet list.
- `#/watchlist` — add, remove, and write or edit a thesis.
- `#/s/{SYMBOL}` — sparkline, thesis, append-only timeline with full evidence.
- `#/system` — provider quota and freshness state, so degradation is visible
  rather than merely experienced.

Hash routing, so the back button works and there is no server config.

---

## Demoing the interesting states

Fixture mode is a small simulator, not a stub. The read cursor is real
(per-symbol `last_seen_seq`, advanced with `max()`), dismissals are persisted
per `(symbol, signal_kind)` for the session, and the budget recomputes.

| To see | Do this |
|---|---|
| **Thesis contradiction** | Top card on load — TATAMOTORS |
| **Correction** | Above the ranked list — WIPRO, always shown |
| **Summary PENDING** | SUNPHARMA card — renders fully from headline + signals |
| **Summary UNAVAILABLE** | *System → Advance replay clock 6h* releases an ETERNAL card |
| **Freshness SUSPECT** | ETERNAL in the quiet list; HDFCBANK after advancing the clock |
| **Dismiss → suppressed++** | Swipe a card left, or "Show fewer like this" |
| **Mark read** | Swipe right, or "Got it" |
| **Inbox zero** | Clear every card |
| **Reduced motion** | macOS: System Settings → Accessibility → Display → Reduce motion |
| **Dark / light** | Toggle top right: system → light → dark |

---

## Notes on behaviour

- **Nothing renders as an empty card.** When `summary_state` is `PENDING` or
  `UNAVAILABLE` the card is built entirely from `headline` + `signals` +
  `evidence`, and says in place why the prose is missing.
- **`SUSPECT` freshness** gets hazard hatching, a colour used nowhere else, and
  a slow flicker — deliberately not a neutral variant of the other chips.
- **Corrections and thesis contradictions are never dismissible** and never
  compete for a budget slot.
- **No advice.** No target, no verdict, no buy/sell verb anywhere in the copy.
  The thesis panel places the user's own sentence next to dated evidence and
  stops there.
- **Accessibility.** Real landmarks and headings, `role="meter"` on the
  attention gauge, `aria-expanded`/`aria-controls` on evidence, live regions on
  toasts and inbox zero, visible focus rings, full keyboard operation (drag is
  an enhancement — every swipe has a button).

## Known gaps

- `GET /stream` (SSE live prices) is opt-in per the contract and is not wired
  up; the client interface has no method for it yet.
- `GET /symbols/{symbol}` and `GET /search` have no fixtures, so fixture mode
  synthesises them deterministically (see `src/api/fixtures.ts`). Live mode
  calls the real endpoints unchanged.
