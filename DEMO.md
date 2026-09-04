# Demo script — 6 minutes

Rehearse this. The build is only as good as the walkthrough, and the two highest-value
moments (contradiction, correction) are easy to skate past if you improvise.

**Setup before you start:** seed data loaded, simulator clock set 3 days back, `GEMINI_API_KEY`
present, a second browser window open (for the multi-device beat), `/health` open in a tab.

---

## 0. Frame it (20s — do not skip)

> "The obvious build is a watchlist with live prices and a 'since your last visit' banner.
> I assumed you'd see that a lot. So I built the version I think should exist: **this is not a
> dashboard, it's a changelog with a read cursor.** It's closer to a git diff than to a stock app."

Do not open the app yet. Land the framing first — everything after reads differently once it lands.

---

## 1. The returning user (60s) — the product in one screen

Fast-forward the clock 3 days (`POST /sim/advance {hours: 72}`), then open the digest.

Point at, in this order:
- **"You were away 3 days. 47 symbol-events happened. Four are worth your attention."**
- The **quiet list** — say this out loud: *"These were checked and had nothing. 'Nothing meaningful changed' is a real answer and most apps can't give it, because they can't tell the difference between nothing happening and nothing being computed."*
- The **suppressed counter** — "three more passed the gate but lost the ranking. The budget is fixed on purpose. If everything is important, nothing is."

---

## 2. Thesis contradiction (90s) — THE moment

Open the Tata Motors card.

> "When you add a stock, you write why in plain language. This user wrote *'watching for margin
> recovery'* in June. JLR margins just fell 180bps and missed consensus by 190."

Let it sit for a beat. Then:

> "This is the thing I most wanted to build and the reason I think most people won't.
> **It's far more valuable to be told your thesis is wrong than to be told it's right**, and it's
> uncomfortable to receive, so products don't ship it. Note what it is *not* doing: it never says
> sell. It checks *your* stated hypothesis against dated evidence and shows you the evidence."

Expand the evidence. Every claim has a source and a timestamp.

**If asked how it scales:** theses are embedded once at write time and **clustered per symbol** —
many users write the same belief in different words. So generation is O(events x distinct beliefs),
which saturates, instead of O(users), which doesn't. Dedupe by semantic belief, not by user.

---

## 3. Drift — the signal nobody else has (45s)

Open Sun Pharma.

> "Down 8.4% over 19 sessions. Largest single day: 1.19%. **No threshold alert on earth fires on
> this** — not 5%, not 3%, nothing. It's the most under-served signal in every watchlist product,
> and it's the one that actually costs people money, because it's invisible right up until you
> look at a 3-month chart."

Second beat: it also broke correlation with Nifty Pharma (0.11 vs 0.78 baseline) — that's the
second confirming factor. **Two factors, or it doesn't get promoted.**

---

## 4. Idiosyncratic move (30s)

On any card, show raw % next to beta-stripped %.

> "Most of a raw percentage move is just the index. Only the residual is news about *this company*.
> Almost every retail app shows you the raw number, which is mostly noise about Nifty."

---

## 5. The correction (45s) — the credibility moment

Open the Wipro correction card.

> "Three days ago we showed this user Wipro down 4.1%. That wasn't a price move — it was an
> unadjusted 1:3 bonus issue. **Any change-detection system that doesn't adjust corporate actions
> before detecting change will page every single user about a fake 80% crash on the next stock
> split.** We adjust at ingest. And when we do get something wrong, corrections are append-only,
> always shown, and never budgeted away — because the user may have acted on the wrong number."

This is the beat that says *production engineer* rather than *hackathon*.

---

## 6. Stale and conflicting data (40s)

Point at the `SUSPECT` chip on Eternal.

> "Two sources disagree by 2.3%. We don't average them and we don't pick one — we mark it
> suspect and **suppress the derived signals**, because a confident wrong answer is worse than
> an honest missing one. Every number on this screen carries its source, its as-of time and its
> freshness state."

---

## 7. Read cursor across devices (40s)

Ack the items. Open the second browser window — already read there.

> "Per user per symbol we keep a monotonic `last_seen_seq`. Merging across devices is `max()` —
> idempotent, commutative, no coordination needed, and acking a stale set can never move the
> cursor backwards. Multi-device sync is one operation, not a sync engine."

Dismiss a card and show the budget refill + the counter increment.

> "Dismissing teaches a per-user threshold for that signal type. Personalisation without an ML
> platform."

---

## 8. Kill the API key (45s) — the one most people won't dare do

Open `/health` — show live Gemini and OpenRouter quota. Then **unset the key and reload.**

The cards still render. Headlines and signals are computed deterministically; only the prose
summary degrades.

> "The LLM is a nice-to-have on top of a deterministic engine, not the engine. Same principle as
> the suspect-data case: when a dependency is unavailable, return the honest partial answer.
> This app runs with no API keys at all."

---

## 9. Close on the number (30s)

> "The whole AI layer runs on a free tier — about 1,500 requests a day. That's not a cost
> compromise, it's the proof. Summarising per user per view at 10,000 users needs **200,000 calls
> a day** — 400 times over the limit, so it can't even be demonstrated. Summarising **once per
> symbol-event and sharing it** needs about 800. **The marginal LLM cost of an additional user is
> zero**, and that falls straight out of splitting the pipeline at the symbol/user boundary."

Stop there. Do not add anything after this line.

---

## Questions you will be asked

| Question | Answer |
|---|---|
| "Why not just alert on 5% moves?" | A 3% move in a large-cap is 4-sigma; in a smallcap it's Tuesday. And a fixed threshold is blind to drift, regime change and correlation breaks — the signals that actually matter. Show Sun Pharma again. |
| "Why no buy/sell recommendations?" | Two reasons. SEBI moved from advisory to enforcement on digital advice in 2026, so it's a compliance landmine. And it's a worse product — reporting what changed with full provenance is more useful than an opinion the user can't audit. |
| "Isn't this over-engineered for 10k users?" | The opposite — at 10k we shard nothing: one Postgres, one Redis, one ingest worker. ~400 msg/s and ~50 rps peak. 10k users isn't a throughput problem, it's a fan-out and cost problem, and those are the only two things the architecture actually addresses. |
| "How does it get to 10M?" | Signal tier is already O(universe), so it doesn't move. User tier is user-scoped with the shard key in the schema — zero cross-shard reads. The thing that breaks first is the `symbol -> subscribers` index; RELIANCE could have 3M members, so shard it by user-shard. I know exactly which line changes. |
| "Why free-tier LLMs, not a real one?" | Deliberate. A hard ceiling is the most honest test of the architecture, and the design doc has the production Claude path costed at ~$200/month for 10k users. It's one implementation of the `Provider` protocol. |
| "What would you build next?" | Delivery timing — batched digests at market close and morning rather than push-on-tick, on a Kafka delayed-message pattern. And widening thesis clustering, which is the piece with the most headroom. |
| "What's the weakest part?" | Crowd-flow needs real user scale to be meaningful; it's simulated here. And contradiction detection is the highest-variance component — it's gated hard and capped precisely because a wrong contradiction is worse than none. |
