"""The detector registry, and the independence map the two-factor gate depends on.

Adding a detector is: write the module, add one line to `DETECTORS`, and declare
which independence family it belongs to. Nothing else in the system needs to know
it exists.
"""

from __future__ import annotations

import logging

from .base import SignalContext
from ..schemas import Signal
from . import (
    absence,
    correlation,
    crowd,
    drift,
    events,
    idiosyncratic,
    regime,
    volume,
)

log = logging.getLogger("watchlist.signals")

DETECTORS = (
    idiosyncratic,
    drift,
    regime,
    correlation,
    volume,
    events,
    absence,
    crowd,
)

# ---------------------------------------------------------------------------
# Independence families.
#
# The two-factor gate counts *distinct families*, not signals. This distinction
# is the whole gate. Three detectors all firing off the same afternoon's price
# action are one observation wearing three hats, and counting them as three
# confirmations would make the gate worse than no gate — it would launder a
# single noisy print into apparent corroboration.
#
# So: IDIOSYNCRATIC_MOVE and DRIFT share the `price` family, because both are
# statements about the return series and a stock cannot independently confirm
# itself. VOLUME_SURPRISE is separate (participation is a different observable),
# CORRELATION_BREAK is separate (cross-sectional), REGIME_CHANGE is separate
# (second moment, not first).
#
# CORPORATE_EVENT and ABSENCE are deliberately in different families even though
# both concern the same scheduled event: the event is the catalyst and the
# absence is the market's response to it. "It reported" and "and nothing
# happened" are genuinely two observations.
# ---------------------------------------------------------------------------
FAMILY: dict[str, str] = {
    "IDIOSYNCRATIC_MOVE": "price",
    "DRIFT": "price",
    "REGIME_CHANGE": "volatility",
    "CORRELATION_BREAK": "cross_sectional",
    "VOLUME_SURPRISE": "participation",
    "CORPORATE_EVENT": "event",
    "ABSENCE": "absence",
    "CROWD_FLOW": "crowd",
    # Never counted toward confirmations — they are always-shown overlays that
    # ride on top of an already-promoted change. Letting a thesis contradiction
    # count as its own confirmation would let one user's stated belief
    # manufacture the evidence bar it is supposed to clear.
    "THESIS_CONTRADICTION": "thesis",
    "CORRECTION": "correction",
}

NON_CONFIRMING = frozenset({"THESIS_CONTRADICTION", "CORRECTION"})


def run_all(ctx: SignalContext) -> list[Signal]:
    """Run every detector over one symbol's context.

    Returns [] for a SUSPECT symbol — sources disagreed beyond tolerance, so we
    suppress the derived signals rather than emit a confident wrong one
    (contracts/API.md, degradation rules). This is enforced once, here, so no
    individual detector has to remember to check.
    """
    if ctx.freshness == "SUSPECT":
        log.debug("%s is SUSPECT — suppressing all derived signals", ctx.symbol)
        return []

    out: list[Signal] = []
    for module in DETECTORS:
        try:
            signal = module.detect(ctx)
        except Exception:  # one bad detector must not lose the other seven
            log.exception("detector %s failed on %s", module.__name__, ctx.symbol)
            continue
        if signal is not None:
            out.append(signal)
    return out


def families(signals: list[Signal]) -> set[str]:
    return {
        FAMILY.get(s.kind, s.kind)
        for s in signals
        if s.kind not in NON_CONFIRMING
    }


def confirmations(signals: list[Signal]) -> int:
    """The number that has to reach 2 before anything is promoted."""
    return len(families(signals))


__all__ = [
    "DETECTORS",
    "FAMILY",
    "NON_CONFIRMING",
    "SignalContext",
    "confirmations",
    "families",
    "run_all",
]
