"""Every endpoint in contracts/API.md, shape-identical to the fixtures.

The read path (`GET /digest`, `GET /watchlist`, `GET /symbols/{symbol}`) never
recomputes a signal — it joins the `cycle:{symbol}` snapshot and any promoted
`Event` rows against the requesting user's profile. That join is the whole
architecture argument in DESIGN.md §4 and §6: everything expensive already
happened in `pipeline.run_cycle`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clock import clock, iso, utc_now
from ..config import settings
from ..db import get_session
from ..kv import kv
from ..llm.cache import hit_rate_24h
from ..llm.embed import best_embed
from ..llm.router import router as llm_router
from ..llm.thesis import generate_verdicts, impact_for_user
from ..models import Dismissal, Event, User, WatchItem
from ..pipeline import run_cycle
from ..schemas import (
    AckRequest,
    AckResponse,
    AddWatchRequest,
    AttentionBudget,
    ChangeItem,
    DigestResponse,
    DismissRequest,
    DismissResponse,
    HealthResponse,
    MarketDataHealth,
    MarketSnapshot,
    PatchWatchRequest,
    Position,
    Provenance,
    PricePoint,
    QuietItem,
    SessionRequest,
    SessionResponse,
    Signal,
    SimAdvanceRequest,
    SimAdvanceResponse,
    SymbolDetail,
    SymbolRef,
    SparklinePoint,
    WatchEntry,
    WatchlistResponse,
)
from ..scoring.attention import ScoredItem, apply_budget, attention_score, is_always_shown
from ..scoring.relevance import UserSymbolProfile, relevance
from ..signals import NON_CONFIRMING
from ..state.cursor import ack as cursor_ack
from ..state.cursor import get_cursor, get_cursors
from ..universe import BY_SYMBOL, SYMBOLS, UNIVERSE, name_of, spec
from .deps import get_current_user, get_or_create_user

log = logging.getLogger("watchlist.api")

router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------


@router.post("/auth/session", response_model=SessionResponse)
async def open_session(body: SessionRequest, session: AsyncSession = Depends(get_session)):
    user = await get_or_create_user(session, body.device_id)
    await session.commit()
    return SessionResponse(user_id=user.id, token=user.token)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _cycle_snapshot(symbol: str) -> dict | None:
    return await kv().get(f"cycle:{symbol}")


async def _fallback_price_provenance(symbol: str) -> tuple[PricePoint, Provenance]:
    """A watched symbol the pipeline has not cycled yet still needs a shape."""
    from ..ingest.simulator import simulator

    sim = simulator()
    q = await sim.quote(symbol)
    if q is None:
        now = iso(utc_now())
        return (
            PricePoint(last=0.0, change_abs=0.0, change_pct=0.0, vol_z=0.0),
            Provenance(source="sim", as_of=now, freshness="STALE", corporate_action_adjusted=False),
        )
    price = PricePoint(
        last=q.last, change_abs=round(q.change_abs, 2), change_pct=round(q.change_pct, 2), vol_z=0.0
    )
    prov = Provenance(
        source=q.source, as_of=iso(q.as_of), freshness="LIVE", corporate_action_adjusted=False
    )
    return price, prov


async def _watch_price_provenance(symbol: str) -> tuple[PricePoint, Provenance]:
    cached = await _cycle_snapshot(symbol)
    if cached is not None:
        return PricePoint(**cached["price"]), Provenance(**cached["provenance"])
    return await _fallback_price_provenance(symbol)


def _book_value(watches: list[WatchItem]) -> float:
    total = sum((w.qty or 0.0) * (w.avg_cost or 0.0) for w in watches)
    return total if total > 0 else 1.0


async def _event_to_change_item(
    session: AsyncSession, event: Event, watch: WatchItem | None, attention: float, is_unread: bool
) -> ChangeItem:
    signals = [Signal(**s) for s in event.signals]
    thesis_impact = None
    if watch is not None and watch.thesis:
        thesis_impact = await impact_for_user(
            session, event.event_id, event.symbol, watch.thesis, watch.thesis_vector
        )
        if thesis_impact is None:
            # This event was promoted before this user's thesis existed (a new
            # watch added after the ingest cycle that created the event), so
            # no verdict was generated for their belief cluster yet. Generate
            # once now -- it is still cached per *cluster*, not per user, so
            # this stays O(events x distinct beliefs) rather than O(users).
            await generate_verdicts(session, event, signals, llm_router())
            await session.commit()
            thesis_impact = await impact_for_user(
                session, event.event_id, event.symbol, watch.thesis, watch.thesis_vector
            )
    return ChangeItem(
        event_id=event.event_id,
        seq=event.seq,
        symbol=event.symbol,
        name=event.name,
        attention=attention,
        confirmations=event.confirmations,
        headline=event.headline,
        summary=event.summary,
        summary_state=event.summary_state,
        signals=signals,
        thesis_impact=thesis_impact,
        price=PricePoint(**event.price),
        provenance=Provenance(**event.provenance),
        first_seen=iso(event.first_seen),
        is_unread=is_unread,
    )


# ---------------------------------------------------------------------------
# watchlist
# ---------------------------------------------------------------------------


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    rows = await session.execute(select(WatchItem).where(WatchItem.user_id == user.id))
    watches = list(rows.scalars())
    cursors = await get_cursors(session, user.id)

    entries: list[WatchEntry] = []
    unread_total = 0
    for w in watches:
        price, prov = await _watch_price_provenance(w.symbol)
        cursor = cursors.get(w.symbol, 0)

        ev_row = await session.execute(
            select(Event.seq)
            .where(Event.symbol == w.symbol)
            .order_by(Event.seq.desc())
            .limit(1)
        )
        latest_seq = ev_row.scalar_one_or_none() or 0
        if latest_seq > cursor:
            unread_total += 1

        entries.append(
            WatchEntry(
                symbol=w.symbol,
                name=name_of(w.symbol),
                thesis=w.thesis,
                thesis_added_at=iso(w.thesis_added_at) if w.thesis_added_at else None,
                position=Position(qty=w.qty, avg_cost=w.avg_cost) if w.qty and w.avg_cost else None,
                muted_kinds=w.muted_kinds or [],
                added_at=iso(w.added_at),
                last_seen_seq=cursor,
                price=price,
                provenance=prov,
            )
        )

    return WatchlistResponse(entries=entries, unread_total=unread_total)


@router.post("/watchlist", response_model=WatchEntry)
async def add_watch(
    body: AddWatchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    symbol = body.symbol.upper()
    if symbol not in BY_SYMBOL:
        raise HTTPException(status_code=404, detail=f"unknown symbol {symbol}")

    existing = await session.execute(
        select(WatchItem).where(WatchItem.user_id == user.id, WatchItem.symbol == symbol)
    )
    watch = existing.scalar_one_or_none()
    now = utc_now()

    if watch is None:
        watch = WatchItem(
            user_id=user.id, symbol=symbol, added_at=now, muted_kinds=[], open_count=0
        )
        session.add(watch)

    if body.thesis is not None:
        watch.thesis = body.thesis
        watch.thesis_added_at = now
        watch.thesis_vector = best_embed(body.thesis)
    if body.position is not None:
        watch.qty = body.position.qty
        watch.avg_cost = body.position.avg_cost

    await session.flush()
    await session.commit()

    price, prov = await _watch_price_provenance(symbol)
    return WatchEntry(
        symbol=symbol,
        name=name_of(symbol),
        thesis=watch.thesis,
        thesis_added_at=iso(watch.thesis_added_at) if watch.thesis_added_at else None,
        position=Position(qty=watch.qty, avg_cost=watch.avg_cost) if watch.qty and watch.avg_cost else None,
        muted_kinds=watch.muted_kinds or [],
        added_at=iso(watch.added_at),
        last_seen_seq=0,
        price=price,
        provenance=prov,
    )


@router.patch("/watchlist/{symbol}", response_model=WatchEntry)
async def patch_watch(
    symbol: str,
    body: PatchWatchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    symbol = symbol.upper()
    existing = await session.execute(
        select(WatchItem).where(WatchItem.user_id == user.id, WatchItem.symbol == symbol)
    )
    watch = existing.scalar_one_or_none()
    if watch is None:
        raise HTTPException(status_code=404, detail="not on watchlist")

    if body.thesis is not None:
        watch.thesis = body.thesis
        watch.thesis_added_at = utc_now()
        watch.thesis_vector = best_embed(body.thesis)
    if body.position is not None:
        watch.qty = body.position.qty
        watch.avg_cost = body.position.avg_cost
    if body.muted is not None:
        watch.muted_kinds = list(body.muted)

    await session.flush()
    await session.commit()

    cursor = await get_cursor(session, user.id, symbol)
    price, prov = await _watch_price_provenance(symbol)
    return WatchEntry(
        symbol=symbol,
        name=name_of(symbol),
        thesis=watch.thesis,
        thesis_added_at=iso(watch.thesis_added_at) if watch.thesis_added_at else None,
        position=Position(qty=watch.qty, avg_cost=watch.avg_cost) if watch.qty and watch.avg_cost else None,
        muted_kinds=watch.muted_kinds or [],
        added_at=iso(watch.added_at),
        last_seen_seq=cursor,
        price=price,
        provenance=prov,
    )


@router.delete("/watchlist/{symbol}", status_code=204)
async def remove_watch(
    symbol: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    symbol = symbol.upper()
    await session.execute(
        delete(WatchItem).where(WatchItem.user_id == user.id, WatchItem.symbol == symbol)
    )
    await session.commit()
    return None


# ---------------------------------------------------------------------------
# digest — the core screen
# ---------------------------------------------------------------------------


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    rows = await session.execute(select(WatchItem).where(WatchItem.user_id == user.id))
    watches = list(rows.scalars())
    cursors = await get_cursors(session, user.id)
    book_value = _book_value(watches)
    now = utc_now()
    # SQLite drops tzinfo on write, so timestamps read back from the DB (like
    # WatchItem.added_at) are naive; compare against a naive "now" here.
    now_naive = now.replace(tzinfo=None)

    scored: list[ScoredItem] = []
    payload: dict[str, ChangeItem] = {}
    quiet: list[QuietItem] = []

    for w in watches:
        cursor = cursors.get(w.symbol, 0)

        ev_row = await session.execute(
            select(Event)
            .where(Event.symbol == w.symbol, Event.is_correction == False)  # noqa: E712
            .order_by(Event.seq.desc())
            .limit(1)
        )
        event = ev_row.scalar_one_or_none()

        corr_rows = await session.execute(
            select(Event)
            .where(Event.symbol == w.symbol, Event.is_correction == True)  # noqa: E712
            .order_by(Event.seq.desc())
        )
        corrections = [e for e in corr_rows.scalars() if e.seq > cursor]

        showed_something = False

        if event is not None and event.seq > cursor:
            showed_something = True
            profile = UserSymbolProfile(
                symbol=w.symbol, qty=w.qty, avg_cost=w.avg_cost, added_at=w.added_at,
                open_count=w.open_count, has_thesis=bool(w.thesis),
            )
            price_last = event.price.get("last", 0.0)
            rel = relevance(profile, price_last, book_value, now_naive)

            item = await _event_to_change_item(session, event, w, 0.0, True)
            verdict = item.thesis_impact.verdict if item.thesis_impact else None
            kinds = tuple(s.kind for s in item.signals)
            att = attention_score(event.surprise, rel, verdict, None, None, kinds)
            item.attention = att

            always = is_always_shown(kinds)
            scored.append(ScoredItem(event_id=event.event_id, symbol=w.symbol, seq=event.seq,
                                     attention=att, kinds=kinds, is_correction=False,
                                     always_shown=always))
            payload[event.event_id] = item

        for corr in corrections:
            showed_something = True
            item = await _event_to_change_item(session, corr, w, 100.0, True)
            scored.append(ScoredItem(event_id=corr.event_id, symbol=w.symbol, seq=corr.seq,
                                     attention=100.0, kinds=("CORRECTION",), is_correction=True,
                                     always_shown=True))
            payload[corr.event_id] = item

        if not showed_something:
            cached = await _cycle_snapshot(w.symbol)
            if cached is not None and not cached.get("promoted"):
                quiet.append(QuietItem(
                    symbol=w.symbol, name=name_of(w.symbol), reason=cached["gate_reason"],
                    change_pct=cached["price"]["change_pct"],
                    provenance=Provenance(**cached["provenance"]),
                ))

    budget = apply_budget(scored, cap=user.attention_cap)
    items = [payload[s.event_id] for s in budget.shown if not s.is_correction]
    corrections_out = [payload[s.event_id] for s in budget.shown if s.is_correction]

    from ..ingest.simulator import simulator
    sim = simulator()

    return DigestResponse(
        generated_at=iso(now),
        last_checked_at=None,
        market=MarketSnapshot(
            state=clock.market_state(), nifty_pct=sim.index_return_pct(), as_of=iso(now)
        ),
        budget=AttentionBudget(cap=budget.cap, shown=len(items) + len(corrections_out), suppressed=budget.suppressed),
        items=items,
        quiet=quiet,
        corrections=corrections_out,
    )


@router.post("/digest/ack", response_model=AckResponse)
async def ack_digest(
    body: AckRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    cursors = await cursor_ack(session, user.id, body.event_ids)
    await session.commit()

    rows = await session.execute(select(WatchItem.symbol).where(WatchItem.user_id == user.id))
    symbols = [r[0] for r in rows.all()]
    all_cursors = await get_cursors(session, user.id)

    unread_total = 0
    for symbol in symbols:
        ev_row = await session.execute(
            select(Event.seq).where(Event.symbol == symbol).order_by(Event.seq.desc()).limit(1)
        )
        latest = ev_row.scalar_one_or_none() or 0
        if latest > all_cursors.get(symbol, 0):
            unread_total += 1

    return AckResponse(acked=len(body.event_ids), cursors=cursors, unread_total=unread_total)


@router.post("/digest/dismiss", response_model=DismissResponse)
async def dismiss(
    body: DismissRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = await session.execute(
        select(Dismissal).where(Dismissal.user_id == user.id, Dismissal.signal_kind == body.signal_kind)
    )
    d = row.scalar_one_or_none()
    if d is None:
        d = Dismissal(user_id=user.id, signal_kind=body.signal_kind, count=0, threshold=0.0,
                      updated_at=utc_now())
        session.add(d)
    d.count += 1
    d.threshold = min(0.65, d.count * 0.2)
    d.updated_at = utc_now()
    await session.flush()
    await session.commit()

    return DismissResponse(ok=True, signal_kind=body.signal_kind, new_threshold=d.threshold)


# ---------------------------------------------------------------------------
# symbol detail
# ---------------------------------------------------------------------------


@router.get("/symbols/{symbol}", response_model=SymbolDetail)
async def symbol_detail(
    symbol: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    symbol = symbol.upper()
    if symbol not in BY_SYMBOL:
        raise HTTPException(status_code=404, detail=f"unknown symbol {symbol}")

    watch_row = await session.execute(
        select(WatchItem).where(WatchItem.user_id == user.id, WatchItem.symbol == symbol)
    )
    watch = watch_row.scalar_one_or_none()
    if watch is not None:
        watch.open_count += 1
        await session.flush()
        await session.commit()

    price, prov = await _watch_price_provenance(symbol)

    ev_rows = await session.execute(
        select(Event).where(Event.symbol == symbol).order_by(Event.seq.desc()).limit(20)
    )
    timeline = []
    for e in ev_rows.scalars():
        item = await _event_to_change_item(session, e, watch, float(e.surprise) * 10.0, False)
        timeline.append(item)

    from ..ingest.corpactions import adjust_closes
    from ..ingest.simulator import simulator

    sim = simulator()
    cur_session = sim.current_session()
    bars = await sim.history_bars(symbol, 30, session=cur_session)
    actions = await sim.corporate_actions(symbol, session=cur_session)
    closes = [b.close for b in bars]
    idxs = [b.session_index for b in bars]
    adjusted, _ = adjust_closes(closes, idxs, actions, known_as_of=cur_session)
    sparkline = [
        SparklinePoint(t=iso(sim.session_ts(b.session_index)), c=round(c, 2))
        for b, c in zip(bars, adjusted, strict=True)
    ]

    return SymbolDetail(
        symbol=symbol, name=name_of(symbol), price=price, provenance=prov,
        thesis=watch.thesis if watch else None, timeline=timeline, sparkline=sparkline,
    )


@router.get("/search", response_model=list[SymbolRef])
async def search(q: str = Query(default="")):
    needle = q.strip().upper()
    if not needle:
        return []
    out = []
    for sp in UNIVERSE:
        if needle in sp.symbol or needle.lower() in sp.name.lower():
            out.append(SymbolRef(symbol=sp.symbol, name=sp.name, exchange="NSE"))
        if len(out) >= 10:
            break
    return out


# ---------------------------------------------------------------------------
# sim controls + health
# ---------------------------------------------------------------------------


@router.post("/sim/advance", response_model=SimAdvanceResponse)
async def sim_advance(body: SimAdvanceRequest, session: AsyncSession = Depends(get_session)):
    from ..ingest.simulator import simulator

    sim = simulator()
    before = sim.current_session()
    clock.advance(body.hours)
    after = sim.current_session()

    result = await run_cycle(session, llm_router(), session_index=after)

    return SimAdvanceResponse(
        now=iso(clock.now()),
        advanced_hours=body.hours,
        sessions_generated=max(0, after - before),
        events_created=result["events_created"] + result["corrections_created"],
        market=MarketSnapshot(
            state=clock.market_state(), nifty_pct=sim.index_return_pct(), as_of=iso(clock.now())
        ),
    )


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)):
    from ..db import active_backend

    llm = llm_router()
    rate = await hit_rate_24h(session)

    return HealthResponse(
        ok=True,
        market_data=MarketDataHealth(source="sim", freshness="LIVE", as_of=iso(clock.now())),
        llm_providers=llm.health(),
        cache_hit_rate_24h=rate,
    )
