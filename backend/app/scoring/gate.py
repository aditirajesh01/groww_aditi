"""The global gate — stage one of two, and the core algorithm.

DESIGN.md §1 traces this to the behavioural finding: alerts requiring 2+
confirming factors cut false positives from roughly 45% to under 20%, and users
past ~100 unfiltered alerts/day make ~22% more impulsive trades. So the gate is
not a performance optimisation that happens to improve quality; it is a quality
mechanism that happens to shed ~99% of the load (DESIGN.md §4), which is why the
LLM bill in §7 is $200/month instead of $105,000.

Stage one asks "is this interesting to *anyone*?" — it is O(universe) and runs
once per symbol per cycle. Stage two (scoring/attention.py) asks "is this
interesting to *you*?" and is O(users), cheap, and runs at read time.

Two rules, and the second is the one that is easy to get wrong:

1.  At least `MIN_CONFIRMATIONS` (2) confirming factors.
2.  They must come from **distinct independence families**. Counting three
    views of the same price move as three confirmations would make the gate
    actively harmful — it would dress a single noisy print up as corroborated
    evidence. See signals/__init__.py for the family map and why DRIFT shares
    a family with IDIOSYNCRATIC_MOVE.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from ..schemas import Signal
from ..signals import NON_CONFIRMING, confirmations, families


@dataclass(frozen=True)
class GateResult:
    passed: bool
    confirmations: int
    families: tuple[str, ...]
    surprise: float
    reason: str

    @property
    def promoted(self) -> bool:
        return self.passed


def surprise_score(signals: list[Signal]) -> float:
    """Aggregate strength, in sigma-ish units.

    Root-sum-square across families rather than a plain sum. Independent
    evidence should compound, but not linearly — two 3σ factors is a stronger
    case than one 6σ factor, and RSS says so while a sum would rate them equal.
    We take the strongest signal within each family first, so a family cannot
    inflate its own weight by firing twice.
    """
    if not signals:
        return 0.0

    by_family: dict[str, float] = {}
    for s in signals:
        if s.kind in NON_CONFIRMING:
            continue
        from ..signals import FAMILY

        fam = FAMILY.get(s.kind, s.kind)
        by_family[fam] = max(by_family.get(fam, 0.0), abs(s.z))

    if not by_family:
        return 0.0
    return float(sum(v * v for v in by_family.values()) ** 0.5)


def evaluate(signals: list[Signal], freshness: str = "LIVE") -> GateResult:
    """Stage-one gate for one symbol."""

    # A SUSPECT symbol should already have had its signals suppressed upstream
    # (signals.run_all). Re-checking here means a future caller that assembles
    # signals by some other route still cannot get a confident wrong answer out.
    if freshness == "SUSPECT":
        return GateResult(
            passed=False,
            confirmations=0,
            families=(),
            surprise=0.0,
            reason="sources disagree beyond tolerance — signals suppressed until reconciled",
        )

    confirming = [s for s in signals if s.kind not in NON_CONFIRMING]
    n = confirmations(signals)
    fams = tuple(sorted(families(signals)))
    surprise = surprise_score(signals)

    if not confirming:
        return GateResult(False, 0, fams, 0.0, "no detector fired")

    if n < settings.min_confirmations:
        strongest = max(confirming, key=lambda s: abs(s.z))
        return GateResult(
            passed=False,
            confirmations=n,
            families=fams,
            surprise=surprise,
            reason=(
                f"{_describe(strongest)} but no second independent factor — "
                f"one short of the two-factor gate"
            ),
        )

    return GateResult(
        passed=True,
        confirmations=n,
        families=fams,
        surprise=surprise,
        reason=f"{n} independent confirming factors ({', '.join(fams)})",
    )


def _describe(signal: Signal) -> str:
    """A human phrase for why a near-miss was a near-miss."""
    kind = signal.kind.replace("_", " ").lower()
    if signal.kind == "REGIME_CHANGE":
        return f"volatility regime shift at {abs(signal.z) / 3.0:.2f} posterior"
    return f"{kind} at {abs(signal.z):.1f}σ"


def quiet_reason(
    signals: list[Signal], result: GateResult, idiosyncratic_z: float | None = None
) -> str:
    """The line shown in `quiet[]`.

    A never-empty contract (contracts/API.md): "nothing meaningful changed" is a
    valid and useful answer, but only if we say what was checked. An empty list
    with no explanation is indistinguishable from a broken pipeline, and the
    whole product promise is that silence is trustworthy.
    """
    if result.reason.startswith("sources disagree"):
        return result.reason

    if result.confirmations >= 1:
        return result.reason

    if idiosyncratic_z is not None and abs(idiosyncratic_z) >= 0.05:
        return (
            f"moved {abs(idiosyncratic_z):.1f}σ on an index-adjusted basis — "
            f"below the {2.0:.1f}σ threshold, no confirming factor"
        )

    return "moved with its sector; nothing idiosyncratic"
