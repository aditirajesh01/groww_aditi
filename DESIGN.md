# Smart Market Watchlist — System Design

> The watchlist is not a dashboard. It is a **changelog with a read cursor**.

Status: design agreed, implementation pending.

---

## 0. Decisions locked

| Decision | Choice |
|---|---|
| Data source | Real API behind an adapter, **plus** a deterministic replay simulator |
| Stack | Python / FastAPI + Postgres + Redis(Valkey) + React |
| Scope | Watch thesis + contradiction detection + all 4 signal types |
| Target | 10,000 users, with a stated path to 10M |

---

## 1. Research basis

Every design choice below traces to a 2026 finding, not to taste.

| Finding | Source | Design consequence |
|---|---|---|
| FY26 shift to long-term ownership: delivery ratios up, F&O turnover down, active derivative traders −20% to ~78.6L, 87.7% loss-making (~Rs 91,685 cr) | SEBI Annual Report FY26 | The user is a **returning holder**, not a scalper. Do not design for a tape. |
| ~78% of active traders use alerts; only ~23% find them actionable. >100 unfiltered alerts/day => ~22% more impulsive trades. Alerts needing **2+ confirming factors** cut false positives ~45% -> <20% | 2025-26 trading-behaviour literature (vendor-cited; directional) | **Two-factor confirmation gate** is the core algorithm. Attention budget is evidence-backed. |
| Alt-data spend ~$2.8bn (+17% YoY); only ~31% use AI for strategy vs 66% for productivity; card transactions #1 category (~17.9%) | Neudata State of Alt Data 2026 | Alpha is in **proprietary data**, not LLM prose. A broker's analogue of card panels is **watchlist flow**. |
| GR-1 portfolio-aware AI analyst: opt-in, consent layers, guardrails, execution controls. F&O risk alerts + optional trading locks. Behavioural nudges for long-term discipline | Groww Next 2026 | Build the **attention substrate GR-1 sits on**, not a competing insights panel. Behaviourally protective, never signal-generating. |
| 2026 = enforcement year for finfluencer / digital advice; traceability required; Project Sudarsan AI surveillance | SEBI 2026 | Every card is **evidence-linked, timestamped, auditable**. A changelog, not an opinion. |
| BOCPD beats GLR/KS on financial series; ~30% fewer false alarms | Bayesian online changepoint detection literature, 2025 | Principled definition of "meaningful change" instead of `abs(pct) > 5`. |

---

## 2. Differentiators

The default build — CRUD + live prices + "% since last visit" + LLM news cards + sparklines — is what the prompt produces unassisted. Assume the panel sees it many times over. We build five things instead.

### (1) Personal materiality, not universal materiality
The same 4% move is front-page for one user and noise for another.
`relevance(user, symbol)` is a function of position size, proximity to cost basis, tenure on the list, open frequency, and stated watch reason.

### (2) Watch thesis + contradiction detection
Adding a stock requires a plain-language reason: *"watching for margin recovery"*, *"want it under Rs 2,400"*, *"hedge for my HDFC position"*.
- "Meaningful change" becomes checkable against an **explicit hypothesis**, not a generic threshold.
- The system surfaces **evidence that contradicts your own stated thesis**. Contradiction beats confirmation and nobody ships it because it is uncomfortable to receive.
- Compliance-clean: we never advise, we check *your* hypothesis against dated evidence.

### (3) Four signals invisible to threshold alerts
- **Idiosyncratic move** — strip index/sector beta. Most of a raw % move is just Nifty; only the residual is news about *this company*.
- **Drift** — 0.4%/day for three weeks trips no alert and is −8%. The most under-served signal in every watchlist product.
- **Regime change** — BOCPD/CUSUM on realised vol. A slow truth invisible to a chart glance.
- **Correlation break** — "TCS and Infosys normally move together; today they didn't."
- Plus **absence**: expected-to-move-and-didn't (earnings day, nothing happened) is information.

### (4) Explicit attention budget
Max N items per session, ranked, competing for slots. If everything is important, nothing is. Dismissal teaches a per-user per-factor threshold — personalisation without an ML platform.

### (5) Watchlist flow as first-party alt-data
Aggregate, k-anonymised: *"net adds to this symbol up 6x this week."* The retail-attention analogue of the card-transaction panel institutions pay for, structurally unavailable to anyone but a broker. Minimum-cohort gate, aggregate only, never individual.

---

## 3. Defining "meaningful change"

Score in units of the symbol's own recent behaviour, never raw percent.

```
surprise = z(idiosyncratic_return | trailing 60d realised vol)
         (+) volume_participation_z
         (+) P(changepoint | BOCPD)
         (+) discrete_event_prior     # earnings, guidance, rating action,
                                      # block deal, promoter pledge, index inclusion

promote  iff  >= 2 independent confirming factors        # the two-factor rule

attention = surprise x relevance(user, symbol)
                     x thesis_impact
                     x (1 - recency_penalty)
```

A 3% move in a stable large-cap is a 4-sigma event; in a smallcap it is Tuesday. The z-framing handles that for free.

---

## 4. Architecture

**Load-bearing insight:** 10,000 users x 50 symbols = 500,000 user-symbol pairs, but the liquid universe is only ~2,000 symbols. Split the pipeline at the symbol/user boundary.

```
                     O(universe) - shared, expensive, computed ONCE
  ┌──────────────────────────────────────────────────────────────────┐
  │  feed adapters ──> normalise ──> corporate-action adjust          │
  │       │                              │                            │
  │  [replay sim]                        v                            │
  │                          vol / z / BOCPD / beta residual          │
  │                          event extraction                         │
  │                                      │                            │
  │                              GLOBAL GATE  (kills ~99%)            │
  │                                      │                            │
  │                          1 LLM summary per symbol-event           │
  │                                      v                            │
  │                       sig:{symbol}  in Redis/Valkey               │
  └──────────────────────────────────────────────────────────────────┘
                                        │
                     O(users) - personal, cheap, computed AT READ
  ┌──────────────────────────────────────────────────────────────────┐
  │   profile vector x signal vector ──> materiality ──> rank         │
  │   read cursor diff ──> unread changelog ──> attention budget      │
  └──────────────────────────────────────────────────────────────────┘
```

- **Fan-out on read** for personal ranking (reads are bursty; compute is arithmetic).
- **Fan-out on write** only for the top-severity push tier, which is rare by construction.
- **Two-stage gate:** global gate ("interesting to anyone?") then per-user gate. ~99% of symbol-ticks die at stage 1. That is the load-shedding story.

### Throughput reality check
- Ingest: 2,000 symbols @ 5s = **~400 msg/s**. Trivial.
- Read peak: 30% of 10k users in a 30-min evening window = ~1.7 rps avg, **~50 rps peak**.

**10,000 users is not a throughput problem.** It is a fan-out, LLM-cost and connection-count problem. Solve exactly those; keep the rest simple.

### State across sessions and devices
Per-user-per-symbol `last_seen_event_seq`, monotonically increasing.
Cross-device merge is `max()` — idempotent, commutative, conflict-free, no coordination. Offline reconciles identically.

### Delivery
Batched digests (close, morning) over push-on-tick, via a scheduled/delayed-message pattern — the same problem Groww's engineering team documented in *Building a Production-Grade Delayed Message System on Kafka*. Sits on primitives they already run.

---

## 5. Sharding

Two partitioning keys, and the tension between them is the whole design.

**Signal tier partitions by `symbol_id`.**
Kafka `md.ticks` partitioned by symbol guarantees per-symbol ordering — mandatory, because a tick and a corporate action for the same symbol processed out of order produces a fake −80% crash. **This tier is O(universe), not O(users): adding users adds zero load.**

**User tier partitions by `user_id`.**
Every query is user-scoped (`WHERE user_id = ?`), so there are **zero cross-shard queries on the read path**. At 10k this is one Postgres; at 10M it is 16 shards of ~600k users. Design for the property now, cash it in later.

**The one structure spanning both — and the thing that breaks first:**
the subscription inverted index `symbol -> set(user_id)`.
- 10k users: 500k entries, Redis sets, ~50MB. Fine.
- 10M users: RELIANCE alone could have 3M subscribers; a single 3M-member set makes `SMEMBERS` a latency bomb.
- Fix: shard by `(symbol, user_shard)` -> `subs:{RELIANCE}:{shard_07}`. Fan-out goes parallel per user-shard, each worker touching only its own Postgres shard. No hot key.

**Hot-symbol power law.** A handful of symbols carry ~100x the median subscriber count, making their partitions hot. Mitigation: sub-partition the top-K by `symbol:bucket` for fan-out. Legal because **ordering is required for signal computation but not for fan-out** — splitting those two concerns is what makes it safe.

**Scoring shards trivially** by user_id: pure function evaluation, no shared state, linear in stateless workers.

**At 10k we shard nothing.** One Postgres, one Redis, one ingest worker, one scoring worker. The *schema* carries the shard key and every query is user-scoped. The design admits sharding; the deployment declines it. Being able to point at the exact line that changes is the answer.

---

## 6. Latency

The read path never touches the compute path.

| Path | Budget | Notes |
|---|---|---|
| tick -> signal in Redis | p99 ~2s | Asynchronous. Nobody is waiting. |
| **open the app (p95)** | **< 200ms e2e** | The only latency a user feels. |
| — signal vectors | 1-2ms | One pipelined Redis round trip for 50 symbols |
| — profile + cursors | 3-5ms | Single indexed user-scoped Postgres query |
| — materiality scoring | < 1ms | 50 symbols x ~10 float ops |
| — LLM summaries | **0ms** | Pre-computed, cache read, never in path |

**The rule that makes it hold: nothing expensive is ever computed in the request path.** A request is a join of pre-computed vectors. That is why one architecture serves 10k and 10M — reads scale horizontally on stateless boxes.

**Tail:** p99 killers are cold cache misses and connection-pool exhaustion. pgbouncer, plus a *degraded-but-correct* mode — on signal-cache miss, render prices marked `STALE` rather than blocking. Never let a slow dependency become a slow page.

**Deliberately not optimised:** tick-to-screen latency. We are not a trading terminal, and sub-50ms quote delivery is irrelevant to a weekly check-in user. Choosing not to optimise, and saying why, is stronger than pretending to do HFT.

---

## 7. LLM cost

The naive design is what kills these products.

**Naive** — summarise per user per view:
10k users x 1 check-in/day x ~20 changed symbols = **200,000 calls/day**
@ ~1.5k in / 300 out => **~$400-1,000/day = $12k-30k/month.** Absurd at 10k users.

**Ours** — summarise per symbol-event, once, shared by every subscriber:
only symbols passing the global gate get summarised (~3-8% of universe on a normal day)
=> **~100-300 calls/day => ~$45/month, flat.**

> **Marginal LLM cost per additional user: 0.** It falls straight out of the symbol/user tier split, and it is the single most important economic property of this architecture.

- Cache key `(symbol, event_id, content_hash)` — a corrected article regenerates; an unchanged one never does.
- **Personalisation is arithmetic, not inference.** The summary is generic and factual ("Q2 gross margin fell 180bps"); the personal part (does this contradict your thesis? how large is your position?) is deterministic scoring on top.
- The one justified per-user inference is thesis contradiction. Bounded by: (a) only when the symbol already passed the global gate *and* the user has a thesis; (b) embed the thesis once at write time, cosine-gate against event embeddings before generating — a cheap retrieval gate in front of expensive generation; (c) hard per-user daily cap.
- Digests are latency-insensitive => batch API / off-peak pricing.

---

## 8. Stale, delayed and conflicting data

- Every number carries **provenance + as-of timestamp + freshness state**: `LIVE / DELAYED / STALE / SUSPECT`. Rendered, not hidden.
- **Sources disagreeing beyond tolerance => mark SUSPECT and suppress the derived signal** rather than emit a confident wrong one. Suppression is the mature answer.
- **Corporate-action adjustment is mandatory before change detection.** A 1:5 split reads as −80%; unadjusted, we page 10,000 users about a fake collapse. This is where naive change detection dies.
- **Corrections are append-only.** A revised print produces a visible correction entry, because the user may have acted on the wrong number. Auditability by construction — and the right posture for SEBI 2026.

---

## 9. Deliberately simple

No streaming ticks by default (SSE opt-in) — avoids 10k idle WebSockets and matches the FY26 user.
No microservice sprawl: one ingest worker, one scoring worker, one API, Postgres + Redis.
No custom ML training. **No recommendation engine, ever, deliberately.**

---

## 10. Prior art surveyed

| Repo | What it is | Verdict |
|---|---|---|
| `Open-Dev-Society/OpenStock` | Watchlist + TradingView charts + daily news email personalised by watchlist | Closest in spirit. Read its news-association code. Still "send me news", not "detect meaningful change". |
| `adrianhajdin/signalist_stock-tracker-app` | Popular tutorial-grade tracker | Likely the starting point for many other candidates. Useful as a map of what to avoid. |
| `Benboerba620/daily-watchlist` | AI watchlist, multi-source quote fallback (Stooq/Finnhub/EOD/yfinance) | **Steal the provider-fallback chain** for the freshness/conflict layer. |
| `shubh123a3/Stock-Market-Anomaly-Detection` | z-score, Isolation Forest, DBSCAN, LSTM, autoencoder | Reference for the anomaly layer; we need online/streaming, not batch. |
| `Barisaksel/finomaly` | Modular rule + ML anomaly library | Good structural reference for a pluggable detector interface. |

**None implement** watch-thesis or contradiction detection, per-user materiality, read-cursor changelog semantics, or drift / correlation-break signals. The differentiators hold.
