"""Thesis contradiction detection, clustered per symbol.

The differentiator nobody ships, because it is uncomfortable to receive: the
system surfaces evidence **against your own stated reason for holding**.
Contradiction beats confirmation.

It is also the feature that most obviously does not scale if you build it the
obvious way. Checking each user's thesis against each event is O(users x events)
— at 10k users that is a five-figure monthly LLM bill for one feature, and at
10M it is not a product.

**The fix is to dedupe by semantic belief rather than by user.** Many people
write the same thing: "watching for margin recovery", "waiting on margins",
"margin recovery play". Embed every thesis once at write time, cluster the
theses per symbol, and generate one verdict per (event, cluster). A symbol
carries maybe 5-20 distinct beliefs no matter how many subscribers it has, so
generation **saturates** instead of growing. That is the single sharpest scaling
idea in DESIGN.md §7 and this module is where it is cashed in.

The full gating chain, in order, cheapest first:

    symbol passed the global gate            (~99% die here)
      -> user has a thesis at all
        -> cosine(event, thesis cluster) > tau     (cheap, local, no LLM)
          -> hard per-user daily cap
            -> generate one verdict per cluster

Only the last step costs a provider call, and it is per *cluster*, not per user.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import utc_now
from ..config import settings
from ..models import Event, ThesisVerdict, WatchItem
from ..schemas import Signal, ThesisImpact
from .base import EvidenceRow, ThesisRequest
from .embed import best_embed, cosine

log = logging.getLogger("watchlist.llm.thesis")


def cluster_id(symbol: str, vector: list[float]) -> str:
    """Stable id for a belief cluster, derived from its centroid.

    Quantising the vector before hashing means two near-identical centroids
    produce the same id, which keeps cluster ids stable as members are added.
    """
    quantised = ",".join(f"{v:.2f}" for v in vector[:32])
    digest = hashlib.blake2b(f"{symbol}|{quantised}".encode(), digest_size=12)
    return f"cl_{digest.hexdigest()}"


@dataclass
class BeliefCluster:
    id: str
    symbol: str
    centroid: list[float]
    exemplar: str
    members: list[int]   # WatchItem ids

    def similarity(self, vector: list[float]) -> float:
        return cosine(self.centroid, vector)


def cluster_theses(
    rows: list[tuple[int, str, list[float]]], tau: float | None = None
) -> list[BeliefCluster]:
    """Greedy single-pass agglomerative clustering by cosine.

    Greedy rather than k-means or DBSCAN because the input is tens of short
    strings per symbol, the cluster count is unknown, and the cost of an
    imperfect merge is one extra LLM call rather than a wrong answer. Spending
    a real clustering algorithm on this would be optimising the wrong thing.

    Rows are `(watch_item_id, thesis_text, vector)`, longest thesis first so the
    most specific phrasing becomes the exemplar sent to the model.
    """
    tau = settings.thesis_cluster_tau if tau is None else tau
    ordered = sorted(rows, key=lambda r: -len(r[1]))
    clusters: list[BeliefCluster] = []

    for item_id, text, vector in ordered:
        if not vector:
            continue
        best: BeliefCluster | None = None
        best_score = 0.0
        for cluster in clusters:
            score = cluster.similarity(vector)
            if score > best_score:
                best, best_score = cluster, score

        if best is not None and best_score >= tau:
            best.members.append(item_id)
            # Running mean centroid, so the cluster drifts toward its members.
            n = len(best.members)
            best.centroid = [
                (c * (n - 1) + v) / n for c, v in zip(best.centroid, vector)
            ]
        else:
            clusters.append(
                BeliefCluster(
                    id=cluster_id("", vector),
                    symbol="",
                    centroid=list(vector),
                    exemplar=text,
                    members=[item_id],
                )
            )

    return clusters


def event_vector(headline: str, signals: list[Signal]) -> list[float]:
    """Embed an event by its headline plus its evidence labels and values.

    Evidence text is included because the headline alone ("Down 6.2% on 3.4x
    volume") rarely contains the vocabulary a thesis is written in. "JLR EBIT
    margin" appears in the evidence, and that is the word that makes a margin
    thesis match.
    """
    parts = [headline]
    for signal in signals:
        parts.append(signal.detail)
        for evidence in signal.evidence:
            parts.append(f"{evidence.label} {evidence.value}")
    return best_embed(" ".join(parts))


async def clusters_for_symbol(
    session: AsyncSession, symbol: str
) -> list[BeliefCluster]:
    """Every distinct belief currently held about one symbol."""
    rows = await session.execute(
        select(WatchItem.id, WatchItem.thesis, WatchItem.thesis_vector).where(
            WatchItem.symbol == symbol, WatchItem.thesis.is_not(None)
        )
    )
    payload: list[tuple[int, str, list[float]]] = []
    for item_id, thesis, vector in rows.all():
        if not thesis:
            continue
        payload.append((item_id, thesis, vector or best_embed(thesis)))

    clusters = cluster_theses(payload)
    for c in clusters:
        c.symbol = symbol
        c.id = cluster_id(symbol, c.centroid)
    return clusters


async def generate_verdicts(
    session: AsyncSession,
    event: Event,
    signals: list[Signal],
    llm_router,
) -> int:
    """Generate one verdict per distinct belief cluster for this event.

    O(events x distinct beliefs). Called from the ingest pipeline, never from
    the read path — by the time a user opens the app the verdict is already a
    row waiting to be joined.
    """
    clusters = await clusters_for_symbol(session, event.symbol)
    if not clusters:
        return 0

    vector = event_vector(event.headline, signals)
    evidence = tuple(
        EvidenceRow(
            label=e.label, value=e.value, as_of=e.as_of, source=e.source
        )
        for s in signals
        for e in s.evidence
    )[:8]

    generated = 0
    for cluster in clusters:
        # --- the cosine gate: cheap, local, kills ~80% before any LLM call ---
        similarity = cluster.similarity(vector)
        if similarity < settings.thesis_contradiction_tau:
            log.debug(
                "%s: cluster %s below tau (%.2f) — no generation",
                event.symbol,
                cluster.id,
                similarity,
            )
            continue

        existing = await session.execute(
            select(ThesisVerdict).where(
                ThesisVerdict.event_id == event.event_id,
                ThesisVerdict.cluster_id == cluster.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        request = ThesisRequest(
            symbol=event.symbol,
            name=event.name,
            event_id=event.event_id,
            cluster_id=cluster.id,
            exemplar_thesis=cluster.exemplar,
            headline=event.headline,
            evidence=evidence,
        )
        verdict = await llm_router.check_thesis(session, request)

        # --- a two-factor gate applied to the verdict itself ---------------
        # Free-tier models reliably write case-specific rationale prose but
        # are known to under-classify and to emit a canned, uncalibrated
        # confidence regardless of the actual case (observed live: NVIDIA's
        # llama-3.2-11b returning NEUTRAL/0.20 on every request, identical
        # across unrelated symbols, while the rationale text plainly engages
        # with the evidence). The same "never trust one signal alone"
        # principle this app applies to price data applies here: cross-check
        # a hedged LLM verdict against the deterministic lexical check before
        # accepting it. The lexical check is free (no network call) and
        # already exists as the template provider's own floor.
        if verdict.get("verdict") == "NEUTRAL" and verdict.get("provider") != "template":
            lexical = await llm_router.template.check_thesis(request)
            if lexical["verdict"] != "NEUTRAL" and lexical["confidence"] > verdict.get(
                "confidence", 0.0
            ):
                log.info(
                    "%s: %s verdict NEUTRAL(%.2f) overridden by lexical %s(%.2f)",
                    event.symbol,
                    verdict.get("provider"),
                    verdict.get("confidence", 0.0),
                    lexical["verdict"],
                    lexical["confidence"],
                )
                verdict = {**lexical, "provider": f"{verdict.get('provider')}+lexical"}

        session.add(
            ThesisVerdict(
                event_id=event.event_id,
                cluster_id=cluster.id,
                symbol=event.symbol,
                exemplar_thesis=cluster.exemplar,
                verdict=verdict["verdict"],
                confidence=float(verdict["confidence"]),
                rationale=verdict["rationale"],
                provider=verdict.get("provider", "template"),
                created_at=utc_now(),
            )
        )
        generated += 1

    await session.flush()
    return generated


async def impact_for_user(
    session: AsyncSession,
    event_id: str,
    symbol: str,
    user_thesis: str | None,
    user_vector: list[float] | None,
) -> ThesisImpact | None:
    """Join a user onto the cluster verdict that matches their belief.

    This is the read-path half and it is deliberately arithmetic: pick the
    stored verdict whose exemplar is closest to this user's thesis. No
    generation, no provider call, no per-user work beyond a cosine over a
    handful of candidates.
    """
    if not user_thesis:
        return None

    rows = await session.execute(
        select(ThesisVerdict).where(ThesisVerdict.event_id == event_id)
    )
    verdicts = list(rows.scalars())
    if not verdicts:
        return None

    vector = user_vector or best_embed(user_thesis)
    best = None
    best_score = -1.0
    for verdict in verdicts:
        score = cosine(vector, best_embed(verdict.exemplar_thesis))
        if score > best_score:
            best, best_score = verdict, score

    if best is None:
        return None

    # A cluster whose exemplar is not actually this user's belief should not
    # speak for them.
    if best_score < settings.thesis_cluster_tau * 0.6:
        return None

    return ThesisImpact(
        thesis=user_thesis,
        verdict=best.verdict,
        confidence=round(float(best.confidence), 2),
        rationale=best.rationale,
    )


def contradiction_signal(
    impact: ThesisImpact, thesis_added_at: str | None, evidence
) -> Signal:
    """Render a CONTRADICTS verdict as a first-class signal on the card."""
    when = f" on {thesis_added_at[:10]}" if thesis_added_at else ""
    return Signal(
        kind="THESIS_CONTRADICTION",
        z=0.0,
        direction="down" if impact.verdict == "CONTRADICTS" else "neutral",
        detail=(
            f'You added this{when} noting "{impact.thesis}". '
            f"The evidence below points the other way."
        ),
        evidence=list(evidence)[:3],
    )
