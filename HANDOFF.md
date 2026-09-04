# Handoff — state as of 2026-09-04

Snapshot for whoever (human or model) picks this up next. Two agents were building
`backend/` and `frontend/` in parallel when this was written, so re-run the inventory
commands below before trusting the "left to do" lists.

```bash
find backend frontend -type f -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/__pycache__/*" | sort
```

---

## Read these first, in order

1. `README.md` — thesis, architecture diagram, and the map from the challenge brief's six
   open decisions to where each is answered.
2. `DESIGN.md` — the full design. Sections 5 (sharding), 6 (latency), 7 (LLM cost) carry the
   distributed-systems reasoning. **Do not re-derive these; they are settled.**
3. `contracts/API.md` + `contracts/types.ts` + `contracts/fixtures/*.json` — **authoritative.**
   Backend and frontend were built in parallel against these. Changing a shape means changing
   all three in the same commit.
4. `DEMO.md` — the walkthrough and the prepared answers to expected pushback.

---

## Non-negotiables (these are decisions, not defaults)

- **Corporate-action adjustment runs BEFORE change detection.** An unadjusted 1:5 split reads
  as -80% and pages every user about a fake crash. This is the top correctness risk.
- **Two-factor gate**: nothing is promoted to "deserves attention" without >= 2 independent
  confirming signals.
- **Read cursor merges with `max()`** — idempotent, commutative, never moves backwards.
- **Summarise per SYMBOL-EVENT, once, shared by all subscribers.** Never per user per view.
  This is what makes marginal LLM cost per user zero and what keeps the app inside a free tier
  (~800 calls/day vs ~200,000 for the naive design).
- **Thesis clustering**: embed each thesis once at write time, cluster per symbol, so
  contradiction detection is O(events x distinct beliefs), not O(users).
- **SUSPECT freshness suppresses derived signals.** A confident wrong answer is worse than an
  honest missing one.
- **Never emit advice, price targets, or buy/sell language.** Every claim must trace to
  `signals[].evidence[]`. This is a deliberate SEBI-2026 compliance posture.
- **The app must run with no API keys at all** (template provider floor) and with no Postgres
  or Redis (sqlite + in-process shim fallbacks).

---

## Done

**Docs / contract** — complete.
`README.md`, `DESIGN.md`, `DEMO.md`, `HANDOFF.md`, `contracts/{API.md,types.ts,fixtures/}`.

**Backend** (`backend/app/`)
- Scaffolding: `config.py`, `db.py`, `models.py`, `schemas.py`, `clock.py`, `kv.py`, `universe.py`
- `ingest/`: `base.py`, `yahoo.py`, `simulator.py` (deterministic replay), `reconciler.py`
  (freshness state machine), `corpactions.py`
- `signals/`: all eight detectors — `idiosyncratic`, `drift`, `regime`, `correlation`,
  `volume`, `events`, `absence`, `crowd` — plus `stats.py`, `base.py`
- `scoring/`: `gate.py` (two-factor), `relevance.py`, `attention.py`
- `state/cursor.py` (read cursor)
- `llm/base.py` (Provider protocol)

**Frontend** (`frontend/src/`)
- Vite + React 19 + TS config, `package.json`
- `api/`: `client.ts`, `fixtures.ts`, `http.ts`, `types.ts` (fixture/live swap via `VITE_USE_FIXTURES`)
- `state/`: `store.tsx`, `router.ts`, `theme.ts`
- `screens/`: `DigestScreen.tsx`, `WatchlistScreen.tsx`
- `components/`: `ChangeCard`, `ThesisConfrontation`, `AttentionMeter`, `Ticker`,
  `FreshnessChip`, `Evidence`, `QuietList`, `InboxZero`, `DigestHeader`, `Sparkline`,
  `Skeleton`, `Toasts`
- `styles/`: `theme.css`, `app.css`; `lib/`: `motion.ts`, `format.ts`, `signals.ts`

---

## Left to do

**Backend — highest priority first**
1. `llm/gemini.py` — Gemini free tier, `gemini-2.5-flash`, `google-genai` SDK (~10 RPM, ~500-1500 RPD)
2. `llm/openrouter.py` — OpenRouter free models (ids ending `:free`), OpenAI-compatible endpoint (20 RPM, 50 RPD at zero balance)
3. `llm/template.py` — deterministic summary from signal evidence. **Required**; the app must work with no keys.
4. `llm/router.py` — cascade gemini -> openrouter -> template; token bucket, daily quota tracker, circuit breaker, backoff. Surface state on `GET /health`.
5. `llm/cache.py` — content-hash cache keyed `(symbol, event_id, content_hash)`
6. `api/` routes — every endpoint in `contracts/API.md`, shape-identical to the fixtures, incl. `POST /sim/advance` and a rich `GET /health`
7. `main.py` — FastAPI app assembly
8. Seed script — ~40 NSE symbols, 3 demo users, reproducing the fixture scenarios: Tata Motors
   thesis contradiction, Sun Pharma drift, HDFC regime change, Infosys absence, Wipro
   correction, Eternal SUSPECT
9. `tests/` — cursor `max()` convergence under out-of-order/duplicate acks; two-factor gate;
   corporate-action adjustment preventing a fake crash; SUSPECT suppression; LLM cascade
   falling through to template
10. `backend/README.md`, `docker-compose.yml`

**Frontend**
1. Symbol detail screen (timeline + sparkline + evidence)
2. `frontend/README.md`
3. Verify dark mode and `prefers-reduced-motion` both actually work
4. Flip `VITE_USE_FIXTURES=false` and confirm the live client matches the fixture shapes

**Integration**
1. Run both, end to end
2. Root `Makefile` for one-command startup
3. Walk `DEMO.md` and confirm every beat actually reproduces

---

## Environment notes

- `python3` is 3.14 — check numeric-lib wheels; `ls /opt/homebrew/bin/python3.*` for 3.12/3.13 if numpy fails.
- Node v22.20.0. `gh` authed as `aditirajesh01` (`repo` scope).
- Remote: `https://github.com/aditirajesh01/groww_aditi.git`. Local clone kept at `~/code/groww_aditi`.
- `GEMINI_API_KEY` / `OPENROUTER_API_KEY` are **optional** — never make them required.

## Cost note for the next model

Orchestrate on a strong model; do the mechanical file-writing on a cheaper one
(`model: "sonnet"` on the Agent tool). Both build agents here inherited Opus by default,
which was the wrong call and burned budget unnecessarily. The design work is finished —
what remains is implementation against a written spec and does not need a frontier model.
