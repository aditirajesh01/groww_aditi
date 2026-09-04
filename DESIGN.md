# Delta — system design

Delta is not a dashboard. It's a changelog with a read cursor: symbols are tracked, changes
are detected against each symbol's own recent behavior, and once a change has been shown to
a user it's marked read and doesn't come back. This document is the reasoning behind that,
kept close to what was actually built. See [README.md](README.md) for a summary and
[contracts/API.md](contracts/API.md) for the endpoint reference.

## Contents

1. [Research basis](#1-research-basis)
2. [What the product does differently](#2-what-the-product-does-differently)
3. [Defining a meaningful change](#3-defining-a-meaningful-change)
4. [Architecture](#4-architecture)
5. [Sharding](#5-sharding)
6. [Latency](#6-latency)
7. [LLM cost](#7-llm-cost)
8. [Stale, delayed, and conflicting data](#8-stale-delayed-and-conflicting-data)
9. [Where the design stays simple](#9-where-the-design-stays-simple)
10. [Related projects](#10-related-projects)
11. [Frontend](#11-frontend)

## 1. Research basis

A few points from 2026 reporting and research shaped the direction of the product.

| Finding | Source | What it implies for the design |
|---|---|---|
| SEBI's FY26 annual report shows a shift toward long-term ownership: delivery ratios up, F&O turnover down, active derivatives traders down about 20% to 78.6 lakh, and 87.7% of individual F&O traders still losing money (roughly ₹91,685 crore in aggregate) | SEBI Annual Report FY26 | The target user is someone checking in periodically, not someone watching a live tape. The product should be designed around that. |
| Around 78% of active traders use some form of alert, but only about 23% find them consistently useful. Traders receiving over 100 unfiltered alerts a day made more impulsive trades. Alerts requiring two or more confirming signals had noticeably lower false-positive rates than single-signal alerts | 2025–26 trading-behavior research (vendor-reported, directional rather than exact) | This is the basis for requiring two independent confirming signals before anything is surfaced, and for capping how many items are shown at once. |
| Spend on alternative data reached roughly $2.8B in 2025, up about 17% year over year; only about 31% of firms use AI for strategy versus 66% for internal productivity; card-transaction data is the largest single category | Neudata, State of the Alternative Data Market 2026 | The interesting data a broker has isn't LLM-generated commentary — it's aggregate watchlist activity across its own users, which nobody else has access to. |
| Groww's GR-1 assistant, announced at Groww Next 2026, is opt-in, portfolio-aware, and built with explicit consent and execution controls; separately, F&O risk alerts include optional trading locks | Groww Next 2026 product announcements | The product should support that kind of assistant rather than compete with it — surfacing what changed and why, not generating trade ideas. |
| SEBI moved from advisory warnings to active enforcement on unregistered digital investment advice in 2026, including AI-based surveillance of finfluencer activity | SEBI 2026 regulatory coverage | Every card needs to trace back to dated, sourced evidence. Nothing in the product should read as advice. |
| Bayesian online changepoint detection outperforms simpler methods (GLR, KS tests) on financial time series, with meaningfully fewer false alarms | Changepoint detection literature, 2025 | Gives a principled way to detect a volatility regime change, instead of an arbitrary percentage threshold. |

## 2. What the product does differently

The straightforward version of this brief is watchlist CRUD, live prices, a percentage
change since your last visit, LLM-written news cards, and sparklines. That's a reasonable
build, and probably a common one. Delta does five things instead:

**Personal materiality.** The same move can matter to one user and not another. Ranking
factors in position size, distance from cost basis, how long the symbol has been on the
list, how often it's opened, and the reason it was added.

**A stated thesis, checked against evidence.** Adding a symbol requires a short,
plain-language reason for watching it — "watching for margin recovery," "want it under
₹2,400," "hedge for my HDFC position." Two things follow from that: a change can be checked
against that specific claim rather than a generic threshold, and the system can flag
evidence that contradicts the stated reason, not just evidence that confirms it.
Contradiction is more useful than confirmation and most products don't build it, probably
because it's an uncomfortable thing to show someone. It's also the safer thing to build —
the app isn't giving advice, it's checking a claim the user already made against dated
evidence.

**Signals a fixed-percentage alert won't catch.** An idiosyncratic move (the price move with
index and sector beta stripped out — most of a raw percentage move on any given day is just
the market, not news about the company). Slow drift (a stock losing half a percent a day for
three weeks trips no alert and is down 8%). A volatility regime change (detected with online
changepoint detection rather than a fixed rule). A correlation break between two symbols that
normally move together. And absence — an event that should have moved the price and didn't.

**A fixed attention budget.** A limited number of ranked slots per digest. Anything that
doesn't make the cut is reported as suppressed rather than silently dropped, and dismissing
an item feeds back into what gets ranked for that user going forward.

**Aggregate watchlist activity as a signal.** Net add/remove activity across users, shown
only in aggregate and only above a minimum cohort size. This is the retail-attention
equivalent of the transaction-panel data institutional investors buy, and it's only
available to a platform that already has the user base.

## 3. Defining a meaningful change

Everything is scored in units of the symbol's own recent behavior, not raw percent change.

```
surprise = z(idiosyncratic return | trailing 60d realised vol)
         + volume participation z
         + P(changepoint | BOCPD)
         + discrete event prior     # earnings, guidance, rating action,
                                     # block deal, promoter pledge, index inclusion

promote  iff  two or more independent confirming factors

attention = surprise x relevance(user, symbol) x thesis_impact x (1 - recency_penalty)
```

A 3% move in a stable large-cap and a 3% move in a small-cap aren't the same event — the
first is several standard deviations out, the second is within normal daily noise. Scoring
in sigma rather than percent handles that without a lookup table of thresholds per stock.

## 4. Architecture

At 10,000 users with roughly 50 symbols on an average watchlist, that's 500,000 user-symbol
pairs — but the liquid symbol universe is only around 2,000 names. The pipeline is split at
that boundary: work that depends only on the symbol is done once and shared; work that
depends on the individual user is done at read time, over already-computed data. The diagram
in [README.md](README.md#architecture) shows this split; the reasoning behind it is below.

- Reads and writes are handled differently on purpose: personal ranking is computed on
  read (reads are what's bursty; the computation itself is arithmetic over two vectors),
  while only the highest-severity push notifications are fanned out on write, and that tier
  is small by construction.
- There's a two-stage gate: a global gate asks whether a change is interesting to anyone at
  all, and only what survives that reaches the per-user gate. In practice the large majority
  of symbol updates don't clear the first gate, which is most of the reason the rest of the
  system stays cheap.

**Rough throughput at 10,000 users:** ingesting ~2,000 symbols every 5 seconds is on the
order of a few hundred messages per second. Read traffic, assuming something like 30% of
users check in during a half-hour evening window, is well under 100 requests per second at
peak. Neither number is a real constraint at this scale — the actual costs are in fan-out and
LLM usage, covered in sections 5 and 7.

**State across sessions and devices.** Each user has a per-symbol `last_seen_event_seq`, a
monotonically increasing counter. Syncing across devices is a `max()` of whatever each device
last saw — commutative, idempotent, and doesn't need any coordination between devices, online
or offline.

**Delivery.** Digests are batched (market close, next morning) rather than pushed on every
tick, using a scheduled/delayed-message pattern. Groww's own engineering blog has a writeup
of a comparable delayed-message system built on Kafka, which is the same kind of pattern this
would sit on in production.

## 5. Sharding

Two different partitioning keys matter here, and the interesting part is how they interact.

The symbol-processing tier partitions by symbol. Per-symbol ordering matters — a corporate
action processed out of order relative to a price tick can register as an ~80% crash that
never happened — so this has to stay ordered per symbol. It scales with the size of the
symbol universe, not the number of users, so adding users doesn't add load here.

The user tier partitions by user ID. Every query is scoped to a single user, so there's no
cross-shard read on that path. At 10,000 users this is one database; at 10 million it would
be on the order of a dozen or more shards, each holding a few hundred thousand users. The
schema is written with that split in mind now, even though nothing is actually sharded yet.

The one structure that spans both is the subscription index — which users are watching which
symbol. At 10,000 users that's around 500,000 entries, comfortably small. At 10 million
users, a single popular symbol could have millions of subscribers, and a lookup against that
one set becomes a real bottleneck. The fix is to shard that index by symbol and a user-shard
suffix, so a fan-out over one symbol becomes several parallel fan-outs, each touching only
its own shard. This works because ordering only matters for signal computation, not for the
fan-out itself — those are separable.

A handful of symbols will always account for a disproportionate share of subscribers, so
those specific partitions run hotter than the rest; the same sub-partitioning approach
handles it.

At the current scale, nothing is actually sharded — one database, one cache, one ingest
process, one scoring process. The point of this section is that the schema and the access
patterns already assume the eventual split, so scaling out later is a deployment change,
not a rewrite.

## 6. Latency

The read path is separated from anything that does real computation.

| Step | Budget | Notes |
|---|---|---|
| Signal update reaches the cache | a couple of seconds | Asynchronous — nothing is waiting on this. |
| Opening the app (target p95) | under 200ms end to end | The only latency a user actually experiences. |
| — reading signal vectors | 1–2ms | One batched cache read for a full watchlist |
| — reading profile and cursor state | a few ms | One indexed, user-scoped database query |
| — scoring | under 1ms | Arithmetic over a small number of symbols |
| — LLM summaries | 0ms on the read path | Already generated and cached; never computed live |

The rule that makes this hold is that nothing expensive runs while a user is waiting — a
request is just a join over data that was already computed. That property is also what lets
the same architecture serve 10,000 users or a much larger number without changing shape,
since the read path doesn't get more expensive as the symbol universe or user base grows.

On the tail end, the usual causes of a slow p99 are a cold cache or exhausted database
connections. The mitigation is a connection pooler plus a degraded-but-correct fallback: if a
signal isn't in cache, show the price marked stale rather than blocking the request. A slow
dependency shouldn't become a slow page.

One thing this deliberately doesn't optimize for is tick-to-screen latency. This isn't a
trading terminal, and sub-second quote delivery isn't relevant to someone checking a
watchlist every few days. Not optimizing for it, and being explicit about why, seems like a
more honest position than building token gestures toward low latency that don't matter for
the actual user.

## 7. LLM cost

### Provider setup

The deployed app runs its LLM layer entirely on free tiers, in this order:

| Provider | Model | Free-tier limits |
|---|---|---|
| Google Gemini | `gemini-flash-latest` | roughly 10 requests/min, several hundred to ~1,500/day |
| OpenRouter | free-tier models | 20 requests/min; 50/day unfunded, 1,000/day after a one-time top-up |
| NVIDIA NIM | `meta/llama-3.2-11b-vision-instruct` | roughly 40 requests/min against a signup credit pool |
| Template | none | deterministic summary composed directly from signal evidence, no network call |

Gemini and OpenRouter both proved unreliable in practice under real traffic — Gemini
returning intermittent 503s, OpenRouter rate-limiting almost immediately even on a fresh key
— which is why NVIDIA NIM was added as a third real option before falling back to the
template. The app runs correctly with none of the three keys configured; the last stop in
the chain needs no key and no network call.

This isn't only a cost decision. Free-tier limits are tight enough (on the order of a
thousand requests a day) that they're a real test of whether the "summarize once per symbol
event" design actually works, rather than something that only pencils out on paper.

| Approach | LLM calls/day at 10,000 users | Fits inside a free tier |
|---|---|---|
| Summarize per user, per view | roughly 200,000 | No — off by a couple orders of magnitude |
| Summarize once per symbol event, shared | roughly 800 | Yes, with headroom |

### Why contradiction checking doesn't scale with users

Checking every user's thesis against every event, done naively, is O(users × events). The
fix is to embed each thesis once when it's written and cluster theses per symbol — many
users describe the same belief in different words ("waiting for margin recovery" and
"watching margins" are the same claim). A symbol typically has somewhere between 5 and 20
distinct belief clusters regardless of how many people are watching it, so generation cost
tracks the number of distinct beliefs, not the number of users. This is the one place in the
design where the naive approach clearly doesn't scale and the fix is worth calling out
directly.

Before anything is generated: the symbol has to have already passed the global gate, the
user has to have a thesis at all, and the thesis's embedding has to be close enough to the
event's embedding to be worth checking. Only a fraction of candidates make it through that
chain, and there's a hard per-user daily cap on top of it.

### If this were running on a paid model

The documented production path is Claude (`claude-opus-5`), using the Batch API (roughly
half the synchronous price) and prompt caching, since digests aren't latency-sensitive and
the system prompt is stable across calls. At current token counts, that works out to
somewhere around $200/month at 10,000 users — split roughly evenly between symbol-event
summaries and thesis-contradiction checks, with embeddings a small fraction of the total.
Switching providers is a matter of implementing one more provider behind the existing
interface; nothing else in the design changes.

A cache entry is only usable once the response that wrote it has started streaming, so
firing many parallel requests against the same prefix pays full price on all of them — the
practical fix is to send one request, wait for the first token, then fire the rest. And
nothing volatile (a timestamp, a request ID) can sit before the cache boundary in the system
prompt, or every request misses.

## 8. Stale, delayed, and conflicting data

Every value carries a source, an as-of timestamp, and a freshness state — live, delayed,
stale, or suspect — and that state is shown, not hidden. When two sources disagree by more
than a set tolerance, the value is marked suspect and any signal derived from it is
suppressed rather than shown with false confidence.

Corporate-action adjustment happens before change detection, not after. An unadjusted 1:5
split shows up as an 80% price drop, and without this step the system would flag a fake
crash on every stock split. Corrections to previously shown numbers are appended rather than
silently overwritten, since a user may have already acted on the earlier figure.

## 9. Where the design stays simple

No streaming price ticks by default — an opt-in live view is available, but it's not the
default, partly to avoid holding open a large number of idle connections and partly because
it doesn't match how the target user actually checks the app. No service sprawl: one ingest
process, one scoring process, one API, and a database plus a cache. No custom-trained models.
And no recommendation engine, deliberately — the product reports what changed and why; it
doesn't suggest what to do about it.

## 10. Related projects

A few existing open-source projects were worth looking at before building this.

| Project | What it does | Relevance |
|---|---|---|
| `Open-Dev-Society/OpenStock` | Watchlist with charts and a daily news email personalized by watchlist | Closest in spirit of the ones reviewed, though it's still "send relevant news," not "detect a meaningful change." |
| `adrianhajdin/signalist_stock-tracker-app` | A widely used tutorial-style tracker | Likely to be the starting point for a fair number of other builds on this brief. |
| `Benboerba620/daily-watchlist` | AI-assisted watchlist with a multi-source quote fallback chain | Worth referencing for how it handles provider fallback. |
| `shubh123a3/Stock-Market-Anomaly-Detection` | Anomaly detection using z-score, Isolation Forest, DBSCAN, LSTM, and autoencoders | Useful reference, though it's a batch approach and this needed something closer to online detection. |
| `Barisaksel/finomaly` | A modular rule- and ML-based anomaly detection library | Reasonable structural reference for a pluggable detector interface. |

None of these implement a stated thesis with contradiction checking, per-user materiality
scoring, read-cursor-based changelog semantics, or drift/correlation-break detection.

## 11. Frontend

The original plan was to build the UI on [Oat](https://github.com/knadh/oat) — a small,
semantic-HTML-first CSS and component library (about 6KB of CSS, a couple KB of JS) with no
dependencies, written by Kailash Nadh, Zerodha's CTO. It's a genuinely well-made library, and
using it would have kept the frontend close to the minimal end of the spectrum.

During implementation this was replaced with Tailwind CSS, styled closer to a dense
dashboard layout (TailAdmin-style), which turned out to be a better fit once the actual
volume of information on screen — signal breakdowns, evidence lists, provider status,
sparklines — became clear. Oat is a component library more suited to simpler, more static
pages; a screen with this much per-item detail and this much conditional state benefited
more from Tailwind's utility classes and the broader ecosystem of examples to build against.

Either way, the choice of CSS layer was never going to be the bottleneck. The actual client
state — read cursors, ranked lists that reorder as items are dismissed, an attention budget
that recomputes — needed a real reactive layer regardless of which CSS approach sat under
it, and React was used for that from the start.
