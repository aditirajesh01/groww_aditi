"""Deterministic seeded replay. The demo centrepiece.

Why this exists rather than "just call Yahoo":

*   A hiring reviewer opening the app at 2am on a Sunday still needs to see a
    market with something happening in it.
*   The interesting cases — an unadjusted corporate action, two sources
    disagreeing, a stale feed — are exactly the cases you cannot summon on
    demand from a real feed, and they are the cases the design claims to handle.
*   `POST /sim/advance {hours}` fast-forwards days of history in one call, so
    "come back in three days and see what changed" is a 30-second demo instead
    of a three-day wait.

Determinism is per-session, not per-call: every value derives from
`hash(seed, session_index, symbol)`, so advancing 72 hours in one request and
24 hours three times produce byte-identical series. That property is what makes
the whole thing reproducible for a reviewer.

The generative model is deliberately the same one the signal engine tries to
invert:

    r_symbol = beta * r_index  +  sector_factor  +  idiosyncratic

`signals/idiosyncratic.py` estimates beta by rolling OLS and reports the
residual. It has to actually recover the structure planted here, which makes the
simulator a test of the engine rather than a puppet show.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from ..clock import clock
from ..config import settings
from ..universe import INDEX_SYMBOL, SECTORS, UNIVERSE, spec
from .base import BarPoint, CorpAction, MarketEvent, Quote

TRADING_DAYS = 252.0


def _seed(*parts: object) -> int:
    raw = "|".join(str(p) for p in parts).encode()
    return int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(), "big")


def _rng(*parts: object) -> np.random.Generator:
    return np.random.default_rng(_seed(settings.sim_seed, *parts))


def _business_days_from(anchor: datetime, offset: int) -> datetime:
    """Anchor + `offset` trading days (Mon-Fri). Negative offsets go back."""
    step = 1 if offset >= 0 else -1
    remaining = abs(offset)
    cursor = anchor
    while remaining:
        cursor += timedelta(days=step)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


# ---------------------------------------------------------------------------
# Scenarios
#
# Each of these exists to make one specific claim in DESIGN.md observable. They
# are anchored relative to S0 (the session at the sim epoch) so a fresh clone
# reproduces every fixture scenario on the very first GET /digest.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    symbol: str
    note: str


SCENARIO_NOTES = {
    "TATAMOTORS": "idiosyncratic crash + volume + earnings miss -> 3 confirmations, contradicts a stated thesis",
    "SUNPHARMA": "19-session drift no daily threshold catches, plus a sector correlation break",
    "HDFCBANK": "realised-vol regime change, confirmed by crowd flow",
    "INFY": "earnings day with an implied move that never materialised (absence)",
    "WIPRO": "1:3 bonus whose notice lands a session late -> unadjusted print -> correction",
    "ETERNAL": "two sources disagreeing by 2.3% -> SUSPECT -> derived signals suppressed",
    "TCS": "a real move with no second confirming factor -> stays quiet by design",
    "DMART": "moved with its sector; nothing idiosyncratic -> stays quiet by design",
}

# Fixed at S0 so the market header matches contracts/fixtures/digest.json.
INDEX_RETURN_AT_S0 = -0.0042

DRIFT_SESSIONS = 19          # SUNPHARMA
REGIME_ONSET_BACK = 22       # HDFCBANK: vol doubles this many sessions before S0
WIPRO_EX_BACK = 2            # bonus ex-date, sessions before S0
WIPRO_NOTICE_LAG = 1         # notice arrives this many sessions after ex-date


class Simulator:
    """A seeded replay of the whole universe, plus the index."""

    name = "sim"

    def __init__(self, history_sessions: int | None = None) -> None:
        self.history = history_sessions or settings.sim_history_sessions
        self.s0 = self.history - 1  # the session sitting at the sim epoch
        self._index: list[float] = []
        self._sector: dict[str, list[float]] = {s: [] for s in SECTORS}
        self._ret: dict[str, list[float]] = {}
        self._vol: dict[str, list[float]] = {}
        self._level: dict[str, list[float]] = {}
        self._index_level: list[float] = []
        self._built_to = -1
        self._stale_symbols: set[str] = set()
        self._suspect_symbols: set[str] = {"ETERNAL"}
        self._extra_actions: list[CorpAction] = []
        self._ensure(self.s0)

    # -- clock -------------------------------------------------------------

    def current_session(self) -> int:
        """Which session the sim clock is standing in."""
        return self.s0 + clock.sessions_elapsed()

    def session_ts(self, i: int) -> datetime:
        """Wall-clock timestamp for a session close, skipping weekends."""
        return _business_days_from(clock.epoch, i - self.s0)

    # -- generation --------------------------------------------------------

    def _ensure(self, upto: int) -> None:
        """Extend every cached path out to `upto`. Pure in session index."""
        if upto <= self._built_to:
            return

        for i in range(self._built_to + 1, upto + 1):
            g = _rng("index", i)
            # ~13% annualised index vol with a small positive drift.
            r_idx = float(g.normal(0.0004, 0.13 / np.sqrt(TRADING_DAYS)))
            if i == self.s0:
                r_idx = INDEX_RETURN_AT_S0
            self._index.append(r_idx)

            for sector in SECTORS:
                gs = _rng("sector", sector, i)
                r_sec = float(gs.normal(0.0, 0.055 / np.sqrt(TRADING_DAYS)))
                if i == self.s0 and sector == "CONSUMER":
                    # Gives DMART a real move that is almost entirely its
                    # sector's — the "moved with its sector" quiet case.
                    r_sec = -0.0140
                self._sector[sector].append(r_sec)

            for sp in UNIVERSE:
                r, vol = self._symbol_session(sp.symbol, i, r_idx,
                                              self._sector[sp.sector][i])
                self._ret.setdefault(sp.symbol, []).append(r)
                self._vol.setdefault(sp.symbol, []).append(vol)

        self._built_to = upto
        self._rebuild_levels(upto)

    def _symbol_session(
        self, symbol: str, i: int, r_idx: float, r_sec: float
    ) -> tuple[float, float]:
        """One session's (return, volume) for one symbol. Deterministic in `i`."""
        sp = spec(symbol)
        g = _rng("sym", symbol, i)
        daily_vol = sp.ann_vol / np.sqrt(TRADING_DAYS)

        beta_load = sp.beta
        vol_mult = 1.0
        vol_shares = sp.base_volume * float(g.lognormal(0.0, 0.28))
        idio = float(g.normal(0.0, daily_vol))

        back = self.s0 - i  # 0 == S0, positive == in the past

        # -- HDFCBANK: realised volatility roughly doubles ------------------
        if symbol == "HDFCBANK" and 0 <= back <= REGIME_ONSET_BACK:
            vol_mult = 2.2
            idio *= vol_mult
            vol_shares *= 1.35

        # -- SUNPHARMA: slow drift + decoupling from its sector -------------
        if symbol == "SUNPHARMA" and 0 <= back < DRIFT_SESSIONS:
            gd = _rng("drift", symbol, i)
            # -0.75%/session median, noise small enough that no single session
            # trips a 1.5% threshold. Cumulative ~= -13%, clearing the drift
            # detector's z-gate against the stock's ordinary (pre-window) vol.
            idio = -0.0075 + float(gd.normal(0.0, 0.0022))
            idio = float(np.clip(idio, -0.0140, 0.0030))
            # The correlation break: it stops loading on its sector factor.
            beta_load = sp.beta * 0.12
            r_sec = r_sec * 0.10

        # -- TATAMOTORS: the idiosyncratic crash with participation ---------
        if symbol == "TATAMOTORS" and back == 0:
            idio = -0.054
            vol_shares = sp.base_volume * 3.4

        # -- INFY: earnings day where nothing happened ----------------------
        # A real but small idiosyncratic move (+0.72%) that nets against the
        # index drag to roughly +0.3% — far under the 4.2% the options market
        # had implied. The *absence* of the expected move is the signal.
        if symbol == "INFY" and back == 0:
            idio = 0.0072
            vol_shares = sp.base_volume * 0.72

        # -- TCS: a genuine single-factor move, no confirmation -------------
        # 2.2σ idiosyncratic, but volume is dead average. One factor. The
        # two-factor gate holds it back and it appears in `quiet` with an
        # explanation — the case that proves the gate is doing work.
        if symbol == "TCS" and back == 0:
            idio = -0.0265
            vol_shares = sp.base_volume * 1.02   # deliberately unremarkable

        # -- DMART: the move is its sector's, not its own -------------------
        if symbol == "DMART" and back == 0:
            idio = 0.0032          # ~0.2σ once beta and sector are stripped
            vol_shares = sp.base_volume * 0.98

        r = beta_load * r_idx + r_sec + idio
        return r, max(vol_shares, 1.0)

    def _rebuild_levels(self, upto: int) -> None:
        """Cumulate returns into price levels, normalised so S0 == base_price."""
        idx_path = np.cumprod(1.0 + np.asarray(self._index[: upto + 1]))
        self._index_level = list(24000.0 * idx_path / idx_path[self.s0])

        for sp in UNIVERSE:
            path = np.cumprod(1.0 + np.asarray(self._ret[sp.symbol][: upto + 1]))
            self._level[sp.symbol] = list(sp.base_price * path / path[self.s0])

    # -- the raw feed ------------------------------------------------------

    def _raw_close(self, symbol: str, i: int) -> float:
        """What the exchange actually quotes on session `i`.

        The economic (adjusted) series is continuous; the *quoted* series has a
        discontinuity at every ex-date, because pre-action prices were on a
        different share count. Inflating history by 1/factor is what reproduces
        that. If nobody adjusts it back out, session `ex_session` reads as a
        catastrophic single-day loss that never happened.
        """
        self._ensure(max(i, self._built_to))
        price = self._level[symbol][i]
        for ca in self._all_actions(symbol):
            if i < ca.ex_session and ca.price_factor != 1.0:
                price = price / ca.price_factor
        return round(price, 2)

    def adjusted_close(self, symbol: str, i: int) -> float:
        """Ground truth, for tests. The engine must recover this from raw."""
        self._ensure(max(i, self._built_to))
        return round(self._level[symbol][i], 2)

    def _all_actions(self, symbol: str) -> list[CorpAction]:
        actions: list[CorpAction] = []
        if symbol == "WIPRO":
            actions.append(
                CorpAction(
                    symbol="WIPRO",
                    kind="bonus",
                    ex_session=self.s0 - WIPRO_EX_BACK,
                    known_at_session=self.s0 - WIPRO_EX_BACK + WIPRO_NOTICE_LAG,
                    ratio_from=1.0,
                    ratio_to=3.0,
                    description="1:3 bonus issue",
                )
            )
        actions.extend(a for a in self._extra_actions if a.symbol == symbol)
        return actions

    # -- FeedAdapter -------------------------------------------------------

    async def quote(
        self, symbol: str, source_id: int = 0, session: int | None = None
    ) -> Quote | None:
        i = self.current_session() if session is None else session
        self._ensure(i)
        if symbol not in self._level:
            return None

        last = self._raw_close(symbol, i)
        prev = self._raw_close(symbol, i - 1) if i > 0 else last
        volume = self._vol[symbol][i]
        as_of = self.session_ts(i)

        # -- injected fault: two sources disagreeing beyond tolerance -------
        if source_id > 0 and symbol in self._suspect_symbols:
            last = round(last * 1.023, 2)

        # -- injected fault: a stale feed ----------------------------------
        if symbol in self._stale_symbols:
            as_of = as_of - timedelta(minutes=45)

        source = self.name if source_id == 0 else f"{self.name}-alt"
        return Quote(
            symbol=symbol,
            last=last,
            prev_close=prev,
            volume=volume,
            as_of=as_of,
            source=source,
            session_index=i,
        )

    async def quotes(
        self, symbols: list[str], source_id: int = 0, session: int | None = None
    ) -> dict[str, Quote]:
        out: dict[str, Quote] = {}
        for s in symbols:
            q = await self.quote(s, source_id=source_id, session=session)
            if q is not None:
                out[s] = q
        return out

    async def history_bars(
        self, symbol: str, sessions: int, session: int | None = None
    ) -> list[BarPoint]:
        i = self.current_session() if session is None else session
        self._ensure(i)
        start = max(0, i - sessions + 1)
        return [
            BarPoint(
                symbol=symbol,
                session_index=j,
                ts=self.session_ts(j),
                close=self._raw_close(symbol, j),
                volume=self._vol[symbol][j],
            )
            for j in range(start, i + 1)
        ]

    async def history(
        self, symbol: str, sessions: int, session: int | None = None
    ) -> list[BarPoint]:
        return await self.history_bars(symbol, sessions, session=session)

    async def index_history(
        self, sessions: int, session: int | None = None
    ) -> list[BarPoint]:
        i = self.current_session() if session is None else session
        self._ensure(i)
        start = max(0, i - sessions + 1)
        return [
            BarPoint(
                symbol=INDEX_SYMBOL,
                session_index=j,
                ts=self.session_ts(j),
                close=round(self._index_level[j], 2),
                volume=0.0,
            )
            for j in range(start, i + 1)
        ]

    def index_return_pct(self, i: int | None = None) -> float:
        i = self.current_session() if i is None else i
        self._ensure(i)
        return round(self._index[i] * 100.0, 2)

    async def corporate_actions(
        self, symbol: str, session: int | None = None
    ) -> list[CorpAction]:
        """Only the actions we have actually been *notified* of by `session`.

        Filtering on `known_at_session` rather than `ex_session` is the entire
        correction mechanism. A feed that returned every action retroactively
        would quietly hide the bug this system is built to survive.
        """
        now = self.current_session() if session is None else session
        return [a for a in self._all_actions(symbol) if a.known_at_session <= now]

    async def corporate_events(self, symbol: str) -> list[MarketEvent]:
        events: list[MarketEvent] = []

        if symbol == "TATAMOTORS":
            events.append(
                MarketEvent(
                    symbol=symbol,
                    session_index=self.s0,
                    kind="earnings",
                    headline="Q1 FY27 results",
                    prior=1.8,
                    implied_move_pct=5.1,
                    payload={
                        "metric": "JLR EBIT margin Q1 FY27",
                        "value": "6.1% (-180bps QoQ)",
                        "consensus": "8.0%",
                        "source": "company filing",
                        "direction": "down",
                        "note": (
                            "JLR EBIT margin 6.1%, down 180bps QoQ, against an "
                            "8.0% consensus. Company cited warranty provisions "
                            "and China mix."
                        ),
                    },
                )
            )

        if symbol == "INFY":
            events.append(
                MarketEvent(
                    symbol=symbol,
                    session_index=self.s0,
                    kind="earnings",
                    headline="Q1 FY27 results; FY27 guidance reiterated",
                    prior=1.8,
                    implied_move_pct=4.2,
                    payload={
                        "metric": "FY27 revenue guidance",
                        "value": "3-5% cc, unchanged",
                        "source": "company filing",
                        "direction": "neutral",
                        "note": (
                            "Revenue 0.4% ahead of consensus; FY27 constant-"
                            "currency guidance reiterated at 3-5%."
                        ),
                    },
                )
            )

        if symbol == "HDFCBANK":
            events.append(
                MarketEvent(
                    symbol=symbol,
                    session_index=self.s0 - REGIME_ONSET_BACK,
                    kind="policy",
                    headline="RBI policy statement",
                    prior=1.2,
                    implied_move_pct=1.4,
                    payload={
                        "metric": "RBI policy statement",
                        "value": "repo unchanged; stance shifted",
                        "source": "RBI",
                        "direction": "neutral",
                        "note": "Coincides with the realised-volatility break.",
                    },
                )
            )

        return events

    # -- demo controls -----------------------------------------------------

    def inject_stale(self, symbol: str, on: bool = True) -> None:
        self._stale_symbols.add(symbol) if on else self._stale_symbols.discard(symbol)

    def inject_disagreement(self, symbol: str, on: bool = True) -> None:
        self._suspect_symbols.add(symbol) if on else self._suspect_symbols.discard(symbol)

    def inject_corporate_action(self, action: CorpAction) -> None:
        """Drop an unadjusted corporate action into the feed on demand."""
        self._extra_actions.append(action)
        self._rebuild_levels(self._built_to)

    def scenario_notes(self) -> dict[str, str]:
        return dict(SCENARIO_NOTES)

    def watch_flow(self, symbol: str) -> list[tuple[int, int, int]]:
        """Aggregate, k-anonymised watchlist adds/removes — DESIGN.md §2(5).

        Real flow comes from `models.WatchFlow`, populated by actual user
        activity; at demo scale there is no such population, so HDFCBANK's
        scenario (regime change *confirmed by crowd flow*, per
        SCENARIO_NOTES) is seeded here the same way every other scripted
        scenario in this file is: deterministically, keyed off `session_index`,
        so a fresh clone reproduces it without a separate seed step.
        """
        if symbol != "HDFCBANK":
            return []
        s0 = self.s0
        g = _rng("crowd", symbol)
        trailing = [
            (s0 - k, int(185 + g.normal(0.0, 22.0)), 6200) for k in range(7, 0, -1)
        ]
        current = (s0, 640, 6200)  # ~3.4x the trailing median, well past MIN_RATIO
        return trailing + [current]


_sim: Simulator | None = None


def simulator() -> Simulator:
    global _sim
    if _sim is None:
        _sim = Simulator()
    return _sim


def reset_simulator() -> Simulator:
    global _sim
    _sim = Simulator()
    return _sim
