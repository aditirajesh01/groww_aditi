"""The compliance filter. Enforced on generated text, not just requested in a prompt.

contracts/API.md: no endpoint returns a recommendation, target price, or
buy/sell language, and every claim in a summary must trace to
`signals[].evidence[]`. DESIGN.md §1 ties this to SEBI's 2026 enforcement
posture on digital advice, where traceability is a requirement rather than a
nicety.

A system prompt asking a model not to give advice is a request. Free-tier models
in particular will cheerfully append "this could be a good entry point" to an
otherwise factual paragraph. So generated text is *checked* before it is stored,
and text that fails is discarded in favour of the deterministic template. Failing
closed costs us some prose quality on rare occasions; failing open costs us the
one property the product is built on.

Two checks:

1.  **Banned language** — advisory verbs, valuation judgements, price targets.
2.  **Number grounding** — every number in the summary must appear in the
    evidence it was generated from. This is the traceability requirement made
    mechanical: a model that invents "margins fell 240bps" when the evidence
    says 180bps gets rejected, even though the sentence reads fine.
"""

from __future__ import annotations

import re

# Advisory / recommendation language. Word-boundary matched, lowercase input.
BANNED_PATTERNS: tuple[str, ...] = (
    r"\bbuy\b", r"\bsell\b", r"\bhold\b", r"\baccumulate\b", r"\bexit\b",
    r"\bbook profits?\b", r"\bavoid\b", r"\bentry point\b", r"\bentry level\b",
    r"\btarget price\b", r"\bprice target\b", r"\bfair value\b", r"\bupside\b",
    r"\bdownside risk\b", r"\bundervalued\b", r"\bovervalued\b", r"\bcheap\b",
    r"\bexpensive\b", r"\battractive\b", r"\bbullish\b", r"\bbearish\b",
    r"\boutperform\b", r"\bunderperform\b", r"\bwe recommend\b", r"\brecommend(s|ed|ation)?\b",
    r"\bshould (buy|sell|consider|hold|exit)\b", r"\bworth (buying|selling|considering)\b",
    r"\bopportunity to\b", r"\bgood time to\b", r"\bconsider (buying|selling|adding|trimming)\b",
    r"\badd to your position\b", r"\btrim\b", r"\bdouble down\b",
    r"\blooks (oversold|overbought|weak|strong)\b", r"\bpoised (to|for)\b",
    r"\bset to (rise|fall|gain|drop)\b", r"\bexpect(ed)? to (rise|fall|rally|drop)\b",
    r"\bwill (rise|fall|rally|drop|recover)\b",
)

_BANNED = tuple(re.compile(p, re.IGNORECASE) for p in BANNED_PATTERNS)

# Numbers, including percentages, basis points and decimals.
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

# Numbers a summary may use without them appearing in evidence: small counts
# ("19 sessions"), years, and quarters are structural, not claims.
_ALLOWED_BARE = {"1", "2", "3", "4", "10", "20", "50", "100"}


class ComplianceFailure(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def find_banned(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in _BANNED:
        match = pattern.search(text)
        if match:
            hits.append(match.group(0))
    return hits


def _numbers(text: str) -> set[str]:
    out = set()
    for raw in _NUMBER.findall(text):
        value = raw.lstrip("-")
        if value.endswith(".0"):
            value = value[:-2]
        out.add(value)
    return out


def ungrounded_numbers(text: str, evidence_blob: str) -> list[str]:
    """Numbers in `text` that do not appear anywhere in the evidence.

    Intentionally forgiving about formatting (a bare `6.1` matches `6.1%`), and
    intentionally strict about existence. The failure mode being caught is a
    model that gets the shape of a financial sentence right and the figure
    wrong, which is both very common and very damaging.
    """
    allowed = _numbers(evidence_blob) | _ALLOWED_BARE
    # Also accept integer forms of evidence decimals, e.g. evidence "3.4x" -> "3".
    allowed |= {v.split(".")[0] for v in list(allowed)}

    bad: list[str] = []
    for value in _numbers(text):
        if value in allowed:
            continue
        if value.split(".")[0] in allowed and "." in value:
            continue
        if len(value) == 4 and value.startswith("20"):  # a year
            continue
        bad.append(value)
    return bad


def check(text: str, evidence_blob: str, strict_numbers: bool = True) -> str:
    """Validate generated text. Raises ComplianceFailure, else returns it."""
    stripped = text.strip()
    if not stripped:
        raise ComplianceFailure("empty")

    banned = find_banned(stripped)
    if banned:
        raise ComplianceFailure("advisory language", ", ".join(sorted(set(banned))))

    if strict_numbers:
        bad = ungrounded_numbers(stripped, evidence_blob)
        if bad:
            raise ComplianceFailure(
                "ungrounded figures", ", ".join(sorted(bad)[:5])
            )

    return stripped


def is_compliant(text: str, evidence_blob: str) -> bool:
    try:
        check(text, evidence_blob)
        return True
    except ComplianceFailure:
        return False
