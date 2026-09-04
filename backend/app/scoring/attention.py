"""The attention score and the attention budget.

    attention = surprise x relevance(user, symbol) x thesis_impact x (1 - recency_penalty)

Straight from DESIGN.md §3. Each term earns its place:

*   **surprise** — how unusual this is, in the symbol's own units. Global.
*   **relevance** — how much it matters to *this* user. Personal.
*   **thesis_impact** — evidence against a belief you wrote down outranks
    evidence that merely happened. Contradiction beats confirmation.
*   **recency_penalty** — the same symbol shouting three days running is one
    story, not three. This is what stops a multi-week drift from occupying a
    slot every single session.

Then the budget: max N items, ranked, competing for slots. If everything is
important, nothing is. `suppressed` is reported honestly — a user should be able
to see that seven things passed the gate and they were shown five, because
hiding the count is how an "attention budget" quietly becomes an excuse for
dropping data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..config import settings
from ..schemas import ALWAYS_SHOWN

# A surprise of ~6 (RSS across a few strong factors) maps to a full score.
SURPRISE_SATURATION = 6.0

THESIS_MULTIPLIER = {
    "CONTRADICTS": 1.45,
    "NEUTRAL": 1.0,
    "SUPPORTS": 1.12,
    None: 1.0,
}

# Half-life of the recency penalty, in sessions.
RECENCY_HALFLIFE = 2.0
RECENCY_MAX = 0.55


@dataclass
class ScoredItem:
    event_id: str
    symbol: str
    seq: int
    attention: float
    kinds: tuple[str, ...]
    is_correction: bool = False
    always_shown: bool = False
    payload: dict = field(default_factory=dict)


def surprise_component(surprise: float) -> float:
    """0..1, saturating. Beyond ~6σ RSS, more sigma is not more attention —
    the user is already going to look."""
    return float(min(1.0, max(0.0, surprise / SURPRISE_SATURATION)))


def recency_penalty(sessions_since_last_shown: int | None) -> float:
    """0 when we have not bothered this user about this symbol recently."""
    if sessions_since_last_shown is None:
        return 0.0
    if sessions_since_last_shown <= 0:
        return RECENCY_MAX
    decay = 0.5 ** (sessions_since_last_shown / RECENCY_HALFLIFE)
    return float(min(RECENCY_MAX, RECENCY_MAX * decay))


def dismissal_damping(kinds: tuple[str, ...], thresholds: dict[str, float]) -> float:
    """A user who keeps dismissing DRIFT cards should see fewer of them.

    Personalisation without an ML platform (DESIGN.md §2(4)): each dismissal
    raises a per-user per-kind threshold, and the threshold damps the score
    multiplicatively. Bounded at 0.35 so a kind can be turned down but never
    silently turned off — that is what `muted_kinds` is for, and muting should
    be a decision the user made on purpose.
    """
    if not thresholds:
        return 1.0
    worst = max((thresholds.get(k, 0.0) for k in kinds), default=0.0)
    return float(max(0.35, 1.0 - min(worst, 0.65)))


def attention_score(
    surprise: float,
    relevance: float,
    thesis_verdict: str | None,
    sessions_since_last_shown: int | None = None,
    dismissal_thresholds: dict[str, float] | None = None,
    kinds: tuple[str, ...] = (),
) -> float:
    """0..100."""
    base = surprise_component(surprise)
    thesis = THESIS_MULTIPLIER.get(thesis_verdict, 1.0)
    penalty = recency_penalty(sessions_since_last_shown)
    damping = dismissal_damping(kinds, dismissal_thresholds or {})

    raw = base * relevance * thesis * (1.0 - penalty) * damping
    return float(round(min(100.0, max(0.0, raw * 100.0)), 1))


@dataclass
class BudgetResult:
    shown: list[ScoredItem]
    suppressed: int
    cap: int


def apply_budget(items: list[ScoredItem], cap: int | None = None) -> BudgetResult:
    """Rank by attention and cut to the cap.

    Two exemptions, both from contracts/types.ts:

    *   **Corrections** are not budgeted at all. They travel in their own
        `corrections[]` array because a user may have acted on the number we
        got wrong, and burying that behind a ranking would be indefensible.
    *   **Thesis contradictions** are never *budgeted away*. They are still
        bounded by `cap`, because contracts/types.ts requires
        `items.length <= budget.cap`, so instead of exempting them from the cap
        we sort them to the front of the queue. In practice a user has a handful
        of theses, not five deep, so this is a guarantee rather than a
        rationing rule.
    """
    cap = cap if cap is not None else settings.attention_cap

    corrections = [i for i in items if i.is_correction]
    rest = [i for i in items if not i.is_correction]

    # Priority key: always-shown first, then attention, then seq for stability.
    rest.sort(key=lambda i: (0 if i.always_shown else 1, -i.attention, -i.seq))

    shown = rest[:cap]
    suppressed = max(0, len(rest) - len(shown))

    return BudgetResult(shown=shown + corrections, suppressed=suppressed, cap=cap)


def is_always_shown(kinds: tuple[str, ...]) -> bool:
    return any(k in ALWAYS_SHOWN for k in kinds)
