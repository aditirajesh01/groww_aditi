"""The two-factor gate: promotion requires >= 2 *independent* confirming
families, not merely 2 signals -- two views of the same price move must not
count twice (DESIGN.md §1, signals/__init__.py)."""

from __future__ import annotations

from app.schemas import Evidence, Signal
from app.scoring.gate import evaluate


def _sig(kind: str, z: float) -> Signal:
    return Signal(kind=kind, z=z, direction="down", detail="x",
                  evidence=[Evidence(label="l", value="v", as_of="2026-01-01T00:00:00Z", source="s")])


def test_single_signal_does_not_promote():
    result = evaluate([_sig("IDIOSYNCRATIC_MOVE", -2.5)])
    assert not result.passed
    assert result.confirmations == 1


def test_two_independent_families_promote():
    result = evaluate([_sig("IDIOSYNCRATIC_MOVE", -2.5), _sig("VOLUME_SURPRISE", 2.1)])
    assert result.passed
    assert result.confirmations == 2


def test_same_family_twice_does_not_promote():
    """IDIOSYNCRATIC_MOVE and DRIFT are both the `price` family -- a stock
    cannot independently confirm itself."""
    result = evaluate([_sig("IDIOSYNCRATIC_MOVE", -2.5), _sig("DRIFT", -2.1)])
    assert not result.passed
    assert result.confirmations == 1


def test_suspect_freshness_suppresses_everything():
    result = evaluate(
        [_sig("IDIOSYNCRATIC_MOVE", -5.0), _sig("VOLUME_SURPRISE", 4.0)],
        freshness="SUSPECT",
    )
    assert not result.passed
    assert "disagree" in result.reason


def test_thesis_contradiction_never_counts_as_its_own_confirmation():
    result = evaluate([_sig("THESIS_CONTRADICTION", 0.0), _sig("IDIOSYNCRATIC_MOVE", -2.5)])
    assert not result.passed
    assert result.confirmations == 1
