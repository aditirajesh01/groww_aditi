"""Multi-source reconciliation and the freshness state machine.

Polls two or more sources for the same symbol, compares them, and produces a
single reconciled quote carrying `LIVE | DELAYED | STALE | SUSPECT`.

The rule that matters (DESIGN.md §8):

    **On SUSPECT we suppress the derived signal rather than emit a confident
    wrong one.**

That is the mature answer and it is genuinely uncomfortable to ship, because
suppression looks like the product doing nothing. It is not doing nothing: it is
declining to tell a user something it cannot stand behind, and `quiet[]` says so
out loud with the disagreement percentage attached. A watchlist that pages you
about a 6% move that only one of its two sources believes in has done more
damage than one that stays silent.

Freshness ladder, worst-wins:

    SUSPECT   sources disagree beyond tolerance          -> suppress signals
    STALE     newest source older than stale_after       -> render, mark
    DELAYED   newest source older than delayed_after     -> render, mark
    LIVE      fresh and in agreement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from ..clock import iso, utc_now
from ..config import settings
from .base import Quote

log = logging.getLogger("watchlist.reconciler")

# Worst-wins ordering.
_RANK = {"LIVE": 0, "DELAYED": 1, "STALE": 2, "SUSPECT": 3}


@dataclass(frozen=True)
class ReconciledQuote:
    symbol: str
    last: float
    prev_close: float
    volume: float
    as_of: datetime
    source: str
    freshness: str
    disagreement_pct: float | None
    session_index: int
    contributors: tuple[str, ...]

    @property
    def suppressed(self) -> bool:
        """SUSPECT means every derived signal for this symbol is withheld."""
        return self.freshness == "SUSPECT"

    @property
    def change_abs(self) -> float:
        return self.last - self.prev_close

    @property
    def change_pct(self) -> float:
        if self.prev_close == 0:
            return 0.0
        return (self.last / self.prev_close - 1.0) * 100.0

    def provenance(self, corporate_action_adjusted: bool) -> dict:
        return {
            "source": self.source,
            "as_of": iso(self.as_of),
            "freshness": self.freshness,
            "disagreement_pct": self.disagreement_pct,
            "corporate_action_adjusted": corporate_action_adjusted,
        }


def _age_seconds(as_of: datetime, now: datetime) -> float:
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return max(0.0, (now - as_of).total_seconds())


def _staleness(as_of: datetime, now: datetime) -> str:
    age = _age_seconds(as_of, now)
    if age >= settings.stale_after_seconds:
        return "STALE"
    if age >= settings.delayed_after_seconds:
        return "DELAYED"
    return "LIVE"


def disagreement(quotes: list[Quote]) -> float:
    """Spread between the highest and lowest print, as a percent of the median.

    Percent-of-median rather than percent-of-first: with three or more sources
    a single bad print should not move the denominator it is being judged
    against.
    """
    if len(quotes) < 2:
        return 0.0
    prices = sorted(q.last for q in quotes)
    mid = prices[len(prices) // 2]
    if mid == 0:
        return 0.0
    return abs(prices[-1] - prices[0]) / mid * 100.0


def reconcile(symbol: str, quotes: list[Quote], now: datetime | None = None) -> ReconciledQuote | None:
    """Fold N source quotes into one, with an honest freshness label."""
    quotes = [q for q in quotes if q is not None]
    if not quotes:
        return None

    now = now or utc_now()
    spread = disagreement(quotes)

    # Primary is the freshest source; ties break on source order so the result
    # is stable across cycles.
    primary = max(quotes, key=lambda q: (q.as_of, q.source))

    state = _staleness(primary.as_of, now)
    disagreement_pct: float | None = None

    if spread > settings.suspect_disagreement_pct:
        state = "SUSPECT"
        disagreement_pct = round(spread, 2)
        log.info(
            "%s marked SUSPECT: sources disagree by %.2f%% (%s) — derived "
            "signals suppressed",
            symbol,
            spread,
            ", ".join(f"{q.source}={q.last}" for q in quotes),
        )

    contributors = tuple(sorted({q.source for q in quotes}))
    source = "+".join(contributors) if len(contributors) > 1 else primary.source

    # With multiple sources agreeing we take the median price rather than the
    # freshest one: agreement is the reason to trust it, so use all of it.
    prices = sorted(q.last for q in quotes)
    last = prices[len(prices) // 2] if state != "SUSPECT" else primary.last

    return ReconciledQuote(
        symbol=symbol,
        last=round(last, 2),
        prev_close=round(primary.prev_close, 2),
        volume=primary.volume,
        as_of=primary.as_of,
        source=source,
        freshness=state,
        disagreement_pct=disagreement_pct,
        session_index=primary.session_index,
        contributors=contributors,
    )


def worst(states: list[str]) -> str:
    """Worst-wins fold, for composing a symbol's freshness with the market's."""
    if not states:
        return "STALE"
    return max(states, key=lambda s: _RANK.get(s, 3))


class Reconciler:
    """Polls 2+ sources per cycle and reconciles them.

    With `FEED_ADAPTER=simulator` the second source is the simulator's own
    alternate feed (`source_id=1`), which is where the injected 2.3%
    disagreement on ETERNAL comes from. With `FEED_ADAPTER=yahoo` the second
    source is the simulator, so a Yahoo outage degrades to SUSPECT/DELAYED
    instead of an empty page.
    """

    def __init__(self, primary, secondary=None) -> None:
        self.primary = primary
        self.secondary = secondary

    async def poll(
        self, symbols: list[str], session: int | None = None
    ) -> dict[str, ReconciledQuote]:
        now = utc_now()
        collected: dict[str, list[Quote]] = {s: [] for s in symbols}

        for source, source_id in ((self.primary, 0), (self.secondary, 1)):
            if source is None:
                continue
            try:
                if session is not None and hasattr(source, "quotes"):
                    try:
                        batch = await source.quotes(
                            symbols, source_id=source_id, session=session
                        )
                    except TypeError:
                        batch = await source.quotes(symbols, source_id=source_id)
                else:
                    batch = await source.quotes(symbols, source_id=source_id)
            except Exception as exc:  # a dead source must not kill the cycle
                log.warning(
                    "source %s failed this cycle (%s) — continuing with the rest",
                    getattr(source, "name", source),
                    type(exc).__name__,
                )
                continue
            for sym, quote in batch.items():
                collected.setdefault(sym, []).append(quote)

        out: dict[str, ReconciledQuote] = {}
        for sym, quotes in collected.items():
            rq = reconcile(sym, quotes, now=now)
            if rq is not None:
                out[sym] = rq
        return out
