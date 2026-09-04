"""The simulation clock.

Everything in the system reads time through this module rather than calling
`datetime.now()` directly. That is what makes `POST /sim/advance {hours}` able
to fast-forward days of market history in one request: advancing the clock
advances the whole system, not just the price generator.

The clock is deterministic — a fresh process always starts at `settings.sim_epoch`
— so a reviewer's first `GET /digest` is byte-identical to the one in the demo.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import settings

IST = timezone(timedelta(hours=5, minutes=30))


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


class SimClock:
    """A monotonic, fast-forwardable UTC clock."""

    def __init__(self, epoch: str | None = None) -> None:
        self._epoch = _parse(epoch or settings.sim_epoch)
        self._offset = timedelta(0)

    @property
    def epoch(self) -> datetime:
        return self._epoch

    def now(self) -> datetime:
        return self._epoch + self._offset

    def advance(self, hours: float) -> datetime:
        """Move forward. Never backwards — a clock that can go back would make
        the globally monotonic `seq` a lie."""
        if hours < 0:
            raise ValueError("the clock only moves forward")
        self._offset += timedelta(hours=hours)
        return self.now()

    def reset(self) -> datetime:
        self._offset = timedelta(0)
        return self.now()

    def elapsed_hours(self) -> float:
        return self._offset.total_seconds() / 3600.0

    def sessions_elapsed(self) -> int:
        """How many whole trading sessions have been generated since the epoch."""
        return int(self.elapsed_hours() // settings.sim_hours_per_session)

    def market_state(self) -> str:
        """NSE cash-market hours in IST, mapped onto the contract's MarketState.

        PRE 09:00-09:15, OPEN 09:15-15:30, POST 15:30-16:00, else CLOSED.
        Weekends are always CLOSED.
        """
        local = self.now().astimezone(IST)
        if local.weekday() >= 5:
            return "CLOSED"
        minutes = local.hour * 60 + local.minute
        if 9 * 60 <= minutes < 9 * 60 + 15:
            return "PRE"
        if 9 * 60 + 15 <= minutes < 15 * 60 + 30:
            return "OPEN"
        if 15 * 60 + 30 <= minutes < 16 * 60:
            return "POST"
        return "CLOSED"


clock = SimClock()


def utc_now() -> datetime:
    return clock.now()


def iso(dt: datetime) -> str:
    """ISO-8601 UTC with a literal Z, exactly as contracts/API.md requires."""
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0, tzinfo=None)
        .isoformat()
        + "Z"
    )


def now_iso() -> str:
    return iso(utc_now())
