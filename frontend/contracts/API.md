# API Contract — authoritative

Both the backend and the frontend implement against **this file** and the JSON
fixtures in `contracts/fixtures/`. Neither side may change a shape here without
updating this file, `contracts/types.ts`, and the fixtures in the same commit.

Base path: `/api/v1`. All timestamps ISO-8601 UTC with `Z`. All money in INR.

## Auth (deliberately trivial — not the point of this project)
`POST /auth/session {device_id}` -> `{user_id, token}`. Bearer token on every call.
A user is a persistent row; the same `device_id` returns the same `user_id`, which
is how "same account, different device" is demonstrated.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/watchlist` | `WatchlistResponse` |
| POST | `/watchlist` | add `{symbol, thesis?, position?}` |
| PATCH | `/watchlist/{symbol}` | update `{thesis?, position?, muted?}` |
| DELETE | `/watchlist/{symbol}` | remove |
| GET | `/digest` | **`DigestResponse` — the core screen** |
| POST | `/digest/ack` | `{event_ids: string[]}` advance read cursor |
| POST | `/digest/dismiss` | `{event_id, signal_kind}` teach a personal threshold |
| GET | `/symbols/{symbol}` | `SymbolDetail` — full timeline + evidence |
| GET | `/search?q=` | `SymbolRef[]` |
| GET | `/stream` | SSE, opt-in live prices only |
| POST | `/sim/advance` | demo control `{hours}` — fast-forward the replay clock |
| GET | `/health` | liveness + per-provider LLM quota state |

## Read-cursor semantics (load-bearing)

Every change carries a globally monotonic `seq`. Per user per symbol we persist
`last_seen_seq`. `GET /digest` returns items with `seq > last_seen_seq` as
`is_unread: true`. `POST /digest/ack` sets `last_seen_seq = max(current, max(acked))`.

**Merge across devices is `max()`** — idempotent, commutative, no coordination.
Acking a stale set can never move the cursor backwards.

## Degradation rules (must be honoured by both sides)

- `summary_state: "PENDING" | "UNAVAILABLE"` means the LLM layer is rate-limited or
  down. The frontend **must still render the item** using `headline` + `signals`,
  which are computed deterministically and never depend on an LLM.
- `provenance.freshness: "SUSPECT"` means sources disagreed beyond tolerance. The
  frontend must visibly mark it and the backend must **suppress derived signals**
  for that symbol rather than emit a confident wrong one.
- A never-empty contract: if nothing passed the gate, `items` is `[]` and `quiet`
  explains what was checked. "Nothing meaningful changed" is a valid, useful answer
  and must be rendered as a deliberate state, not an empty list.

## Never

No endpoint returns a recommendation, target price, or buy/sell language. Every
claim in `summary` must be traceable to an entry in `signals[].evidence[]`.
