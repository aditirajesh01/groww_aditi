"""The ingest cycle: reconcile -> adjust -> detect -> gate -> promote.

Runs once per demo "tick" (startup, and every `POST /sim/advance`). O(universe),
never O(users) — DESIGN.md §4. For every symbol we compute a full signal vector
and cache the cycle snapshot in `kv()` under `cycle:{symbol}` (this stands in for
`sig:{symbol}` in Redis) so the read path (`GET /digest`) never recomputes a
signal; it only joins a precomputed vector against a user profile.

Symbols that pass the two-factor gate become an `Event` row, shared by every
subscriber. Symbols that do not still get their cycle snapshot cached, which is
what lets the digest render an honest `quiet[]` reason instead of silence.

WIPRO's correction is handled as one targeted extra step rather than a general
multi-session replay: the simulator encodes a bonus whose notice arrives one
session after the ex-date (see ingest/simulator.py), and by the time this cycle
runs the notice has already landed. We recompute what *would* have been
published before the notice arrived and diff it against the corrected series
via `ingest.corpactions.restatement`, which is the exact mechanism DESIGN.md §8
describes.
"""

from __future__ import annotations

import logging

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .clock import iso, utc_now
from .ingest.corpactions import adjust_closes, restatement
from .ingest.reconciler import Reconciler, ReconciledQuote
from .ingest.simulator import simulator
from .kv import kv
from .llm.base import EvidenceRow, SummaryRequest
from .llm.router import LLMRouter
from .llm.thesis import generate_verdicts
from .models import Event
from .schemas import Evidence, PricePoint, Provenance, Signal
from .scoring.gate import evaluate, quiet_reason
from .signals import run_all
from .signals.base import SignalContext
from .signals.stats import rolling_ols, zscore
from .state.cursor import allocate_seq
from .universe import TRACKED_PAIRS, UNIVERSE, name_of, sector_peers

log = logging.getLogger("watchlist.pipeline")

HISTORY_SESSIONS = 220
OLS_WINDOW = 60
VOL_WINDOW = 20


def _headline(name: str, price: PricePoint, signals: list[Signal]) -> str:
    direction = "up" if price.change_pct > 0 else "down" if price.change_pct < 0 else "flat"
    if signals:
        strongest = max(signals, key=lambda s: abs(s.z))
        label = strongest.kind.replace("_", " ").title()
    else:
        label = "Change"
    return f"{name} {direction} {abs(price.change_pct):.1f}% — {label}"


def _idio_and_volz(ctx: SignalContext) -> tuple[float | None, float]:
    idio_pct: float | None = None
    if ctx.returns.size >= 20 and ctx.index_returns.size >= 20:
        fit = rolling_ols(ctx.returns, ctx.index_returns, window=OLS_WINDOW)
        idio_pct = round(fit.residual(ctx.last_return, ctx.last_index_return) * 100.0, 2)

    vol_z = 0.0
    if ctx.volumes.size >= 6:
        hist = ctx.volumes[-(VOL_WINDOW + 1) : -1]
        if hist.size >= 3:
            vol_z = round(
                zscore(float(np.log(max(ctx.volumes[-1], 1.0))),
                       np.log(np.clip(hist, 1.0, None))),
                2,
            )
    return idio_pct, vol_z


async def _build_context(
    sp,
    session_index: int,
    rq: ReconciledQuote,
    returns_by_symbol: dict[str, np.ndarray],
    idx_returns_full: np.ndarray,
    idx_closes_full: np.ndarray,
    volumes_by_symbol: dict[str, np.ndarray],
    sim,
) -> SignalContext:
    symbol = sp.symbol
    rets = returns_by_symbol.get(symbol, np.zeros(0))
    n = rets.size
    idx_rets = idx_returns_full[-n:] if n and idx_returns_full.size >= n else np.zeros(0)
    volumes = volumes_by_symbol.get(symbol, np.zeros(0))
    if n:
        volumes = volumes[-n:]

    peer_returns: dict[str, np.ndarray] = {}
    for a, b in TRACKED_PAIRS:
        partner = b if a == symbol else (a if b == symbol else None)
        if partner and partner in returns_by_symbol:
            pr = returns_by_symbol[partner]
            m = min(pr.size, n)
            if m:
                peer_returns[partner] = pr[-m:]

    sector_returns = None
    peers_in_sector = [p for p in sector_peers(symbol) if p in returns_by_symbol][:6]
    arrs = []
    for p in peers_in_sector:
        pr = returns_by_symbol[p]
        m = min(pr.size, n)
        if m > 0:
            arrs.append(pr[-m:])
    if arrs:
        minlen = min(a.size for a in arrs)
        if minlen > 0:
            stacked = np.stack([a[-minlen:] for a in arrs])
            sector_returns = np.mean(stacked, axis=0)

    events = await sim.corporate_events(symbol)
    flow = sim.watch_flow(symbol)

    return SignalContext(
        symbol=symbol,
        name=sp.name,
        spec=sp,
        session_index=session_index,
        as_of=iso(rq.as_of),
        closes=np.zeros(0),
        returns=rets,
        index_returns=idx_rets,
        index_closes=idx_closes_full[-(n + 1):] if n else np.zeros(0),
        volumes=volumes,
        peer_returns=peer_returns,
        sector_returns=sector_returns,
        events=events,
        flow=flow,
        freshness=rq.freshness,
        change_pct=rq.change_pct,
    )


async def _promote(
    db: AsyncSession, sp, session_index: int, signals: list[Signal], gate,
    price: PricePoint, provenance: Provenance, as_of: str, llm: LLMRouter,
) -> Event | None:
    symbol = sp.symbol
    existing = await db.execute(
        select(Event).where(Event.symbol == symbol, Event.session_index == session_index,
                             Event.is_correction == False)  # noqa: E712
    )
    if existing.scalar_one_or_none() is not None:
        return None

    headline = _headline(sp.name, price, signals)
    evidence_rows = tuple(
        EvidenceRow(label=e.label, value=e.value, as_of=e.as_of, source=e.source)
        for s in signals for e in s.evidence
    )[:10]

    (seq,) = await allocate_seq(db, 1)
    event_id = f"evt_{symbol.lower()}_{session_index}_{seq}"

    summary_req = SummaryRequest(
        symbol=symbol, name=sp.name, event_id=event_id, headline=headline,
        signal_kinds=tuple(s.kind for s in signals), evidence=evidence_rows,
        change_pct=price.change_pct, idiosyncratic_pct=price.idiosyncratic_pct, as_of=as_of,
    )
    completion = await llm.summarise(db, summary_req)

    event = Event(
        event_id=event_id, seq=seq, symbol=symbol, name=sp.name, session_index=session_index,
        headline=headline, summary=completion.text, summary_state="READY",
        summary_provider=completion.provider, content_hash=summary_req.content_hash(),
        signals=[s.model_dump() for s in signals], confirmations=gate.confirmations,
        surprise=gate.surprise, is_correction=False,
        price=price.model_dump(), provenance=provenance.model_dump(),
        first_seen=utc_now(),
    )
    db.add(event)
    await db.flush()

    await generate_verdicts(db, event, signals, llm)
    return event


async def _wipro_correction(
    db: AsyncSession, session_index: int, sim, price: PricePoint, provenance: Provenance,
    llm: LLMRouter,
) -> Event | None:
    symbol = "WIPRO"
    actions = await sim.corporate_actions(symbol, session=session_index)
    bonus = next((a for a in actions if a.kind == "bonus"), None)
    if bonus is None:
        return None

    bars = await sim.history_bars(symbol, HISTORY_SESSIONS, session=session_index)
    closes = [b.close for b in bars]
    idxs = [b.session_index for b in bars]
    if bonus.ex_session not in idxs:
        return None
    pos = idxs.index(bonus.ex_session)
    if pos == 0:
        return None

    adjusted_pre, _ = adjust_closes(closes, idxs, actions, known_as_of=bonus.ex_session)
    prev = adjusted_pre[pos - 1]
    published_pct = (adjusted_pre[pos] / prev - 1.0) * 100.0 if prev else 0.0

    r = restatement(
        symbol=symbol, session_index=bonus.ex_session, published_pct=published_pct,
        raw_closes=closes, session_indices=idxs, actions=actions, known_as_of=session_index,
    )
    if r is None:
        return None

    event_id = f"evt_{symbol.lower()}_correction_{r.session_index}"
    existing = await db.execute(select(Event).where(Event.event_id == event_id))
    if existing.scalar_one_or_none() is not None:
        return None

    as_of = iso(sim.session_ts(session_index))
    evidence = [
        Evidence(label="Corporate action", value=r.description, as_of=as_of, source="exchange notice"),
        Evidence(label="Originally published session change", value=f"{r.published_pct:+.2f}%",
                  as_of=as_of, source="watchlist"),
        Evidence(label="Restated session change", value=f"{r.corrected_pct:+.2f}%",
                  as_of=as_of, source="watchlist"),
    ]
    signal = Signal(
        kind="CORRECTION", z=0.0, direction="neutral",
        detail=(f"A {r.description} was applied after the original print; restated "
                f"session change {r.corrected_pct:+.2f}% (was {r.published_pct:+.2f}%)."),
        evidence=evidence,
    )
    headline = f"{name_of(symbol)} correction — {r.description}"
    evidence_rows = tuple(
        EvidenceRow(label=e.label, value=e.value, as_of=e.as_of, source=e.source) for e in evidence
    )
    summary_req = SummaryRequest(
        symbol=symbol, name=name_of(symbol), event_id=event_id, headline=headline,
        signal_kinds=("CORRECTION",), evidence=evidence_rows,
        change_pct=r.corrected_pct, idiosyncratic_pct=None, as_of=as_of,
    )
    completion = await llm.summarise(db, summary_req)

    (seq,) = await allocate_seq(db, 1)
    event = Event(
        event_id=event_id, seq=seq, symbol=symbol, name=name_of(symbol),
        session_index=r.session_index, headline=headline, summary=completion.text,
        summary_state="READY", summary_provider=completion.provider,
        content_hash=summary_req.content_hash(), signals=[signal.model_dump()],
        confirmations=0, surprise=0.0, is_correction=True,
        price=price.model_dump(), provenance=provenance.model_dump(), first_seen=utc_now(),
    )
    db.add(event)
    await db.flush()
    return event


async def run_cycle(db: AsyncSession, llm: LLMRouter, session_index: int | None = None) -> dict:
    """One full pass over the universe. Returns a small summary for logging/API."""
    sim = simulator()
    session_index = sim.current_session() if session_index is None else session_index
    recon = Reconciler(sim, sim)

    idx_bars = await sim.index_history(HISTORY_SESSIONS, session=session_index)
    idx_closes_full = np.array([b.close for b in idx_bars], dtype=float)
    idx_returns_full = (
        np.diff(idx_closes_full) / idx_closes_full[:-1] if idx_closes_full.size > 1 else np.zeros(0)
    )

    all_symbols = [sp.symbol for sp in UNIVERSE]
    quotes = await recon.poll(all_symbols, session=session_index)

    returns_by_symbol: dict[str, np.ndarray] = {}
    volumes_by_symbol: dict[str, np.ndarray] = {}
    adjusted_flag: dict[str, bool] = {}

    for sp in UNIVERSE:
        symbol = sp.symbol
        rq = quotes.get(symbol)
        if rq is None:
            continue
        bars = await sim.history_bars(symbol, HISTORY_SESSIONS, session=session_index)
        actions = await sim.corporate_actions(symbol, session=session_index)
        closes = [b.close for b in bars]
        idxs = [b.session_index for b in bars]
        adj_closes, was_adjusted = adjust_closes(closes, idxs, actions, known_as_of=session_index)
        adjusted_flag[symbol] = was_adjusted
        adj = np.array(adj_closes, dtype=float)
        returns_by_symbol[symbol] = np.diff(adj) / adj[:-1] if adj.size > 1 else np.zeros(0)
        volumes_by_symbol[symbol] = np.array([b.volume for b in bars[1:]], dtype=float)

    events_created = 0
    correction_price: PricePoint | None = None
    correction_provenance: Provenance | None = None

    for sp in UNIVERSE:
        symbol = sp.symbol
        rq = quotes.get(symbol)
        if rq is None:
            continue

        ctx = await _build_context(
            sp, session_index, rq, returns_by_symbol, idx_returns_full, idx_closes_full,
            volumes_by_symbol, sim,
        )
        signals = run_all(ctx)
        gate = evaluate(signals, freshness=rq.freshness)

        idio_pct, vol_z = _idio_and_volz(ctx)
        price = PricePoint(
            last=rq.last, change_abs=round(rq.change_abs, 2), change_pct=round(rq.change_pct, 2),
            idiosyncratic_pct=idio_pct, since_last_seen_pct=None, vol_z=vol_z, currency="INR",
        )
        provenance = Provenance(**rq.provenance(adjusted_flag.get(symbol, False)))

        if symbol == "WIPRO":
            correction_price, correction_provenance = price, provenance

        reason = quiet_reason(signals, gate, idiosyncratic_z=(
            next((s.z for s in signals if s.kind == "IDIOSYNCRATIC_MOVE"), None)
        ))

        await kv().set(f"cycle:{symbol}", {
            "session_index": session_index,
            "price": price.model_dump(),
            "provenance": provenance.model_dump(),
            "gate_reason": reason,
            "confirmations": gate.confirmations,
            "promoted": gate.passed,
        })

        if gate.passed:
            event = await _promote(db, sp, session_index, signals, gate, price, provenance,
                                   iso(rq.as_of), llm)
            if event is not None:
                events_created += 1

    corrections_created = 0
    if correction_price is not None and correction_provenance is not None:
        corr = await _wipro_correction(db, session_index, sim, correction_price,
                                        correction_provenance, llm)
        if corr is not None:
            corrections_created = 1

    await db.commit()
    log.info(
        "cycle complete: session=%d events=%d corrections=%d",
        session_index, events_created, corrections_created,
    )
    return {
        "session_index": session_index,
        "events_created": events_created,
        "corrections_created": corrections_created,
    }
