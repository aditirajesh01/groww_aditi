"""The deterministic summariser. No API key, no network, no quota, never fails.

This is the floor of the cascade and the reason `GET /digest` is fully useful
with zero configuration. It is not a degraded mode with an apology in it — it
composes the same evidence rows the LLM providers are handed, in a fixed
grammar, and the result is a paragraph a user can act on.

Worth being blunt about what that implies: **the LLM is a presentation layer
here, not an analysis layer.** Everything that decides whether you are told
something — the beta-stripped residual, the two-factor gate, the changepoint
posterior, the personal relevance score — is deterministic arithmetic that
happens before any provider is contacted. The model rewrites evidence into
prose. That is a genuinely useful job, and it is also a job a template can do
adequately, which is exactly why the product does not fall over when the free
tier runs out at 3pm.

Two properties by construction:

*   Every claim comes from an evidence row, so the traceability requirement in
    contracts/API.md holds trivially.
*   No advisory language exists in the grammar, so compliance.check() on this
    output is a formality rather than a filter.
"""

from __future__ import annotations

import json

from .base import SummaryRequest, ThesisRequest

# Ordered by how much a reader cares, not alphabetically. The first clause of
# the paragraph should be the most consequential thing that happened.
KIND_ORDER = (
    "CORRECTION",
    "THESIS_CONTRADICTION",
    "CORPORATE_EVENT",
    "IDIOSYNCRATIC_MOVE",
    "DRIFT",
    "REGIME_CHANGE",
    "ABSENCE",
    "CORRELATION_BREAK",
    "VOLUME_SURPRISE",
    "CROWD_FLOW",
)


def _find(req: SummaryRequest, *labels: str) -> str | None:
    for row in req.evidence:
        for label in labels:
            if label.lower() in row.label.lower():
                return row.value
    return None


def _clause(kind: str, req: SummaryRequest) -> str | None:
    """One sentence per signal kind, composed strictly from evidence values."""

    if kind == "CORRECTION":
        restated = _find(req, "Restated session change")
        action = _find(req, "Corporate action")
        if restated and action:
            return (
                f"A {action} was applied after the original print; the restated "
                f"session change is {restated}."
            )
        return None

    if kind == "CORPORATE_EVENT":
        parts = []
        for row in req.evidence:
            if row.source in ("company filing", "exchange notice", "street aggregate", "RBI"):
                parts.append(f"{row.label} was {row.value}")
        if parts:
            return f"{'; '.join(parts[:2])}.".capitalize()
        return None

    if kind == "IDIOSYNCRATIC_MOVE":
        residual = _find(req, "Beta-adjusted residual")
        explained = _find(req, "Explained by index")
        if residual:
            base = f"The session move was {req.change_pct:+.1f}%, of which {residual} is idiosyncratic"
            return f"{base} once the index contribution of {explained} is removed." if explained else f"{base}."
        return None

    if kind == "DRIFT":
        cumulative = _find(req, "Cumulative")
        largest = _find(req, "Largest single-day")
        if cumulative and largest:
            return (
                f"The cumulative move is {cumulative} with no single session "
                f"larger than {largest}, which is why no daily threshold reported it."
            )
        return None

    if kind == "REGIME_CHANGE":
        posterior = _find(req, "Changepoint posterior")
        vol = _find(req, "Realised volatility")
        if posterior and vol:
            return (
                f"Realised volatility moved {vol}, with a changepoint posterior "
                f"of {posterior}."
            )
        return None

    if kind == "ABSENCE":
        implied = _find(req, "Implied vs realised")
        event = _find(req, "Scheduled event")
        if implied:
            lead = f"{event}: " if event else ""
            return f"{lead}the move was {implied}, so the expected volatility did not materialise."
        return None

    if kind == "CORRELATION_BREAK":
        corr = _find(req, "correlation")
        if corr:
            return f"Rolling correlation came in at {corr}."
        return None

    if kind == "VOLUME_SURPRISE":
        ratio = _find(req, "Volume vs")
        if ratio:
            return f"Volume ran at {ratio} the 20-day average."
        return None

    if kind == "CROWD_FLOW":
        ratio = _find(req, "Net adds vs median")
        cohort = _find(req, "Cohort size")
        if ratio:
            tail = f" across a cohort of {cohort.split(' ')[0]} users" if cohort else ""
            return f"Net watchlist adds ran at {ratio} the trailing weekly median{tail}."
        return None

    if kind == "THESIS_CONTRADICTION":
        return None  # carried by ThesisImpact.rationale, not the summary

    return None


class TemplateProvider:
    """Always available, always compliant, always instant."""

    name = "template"

    @property
    def configured(self) -> bool:
        return True

    async def summarise(self, req: SummaryRequest) -> str:
        kinds = [k for k in KIND_ORDER if k in req.signal_kinds]
        clauses = [c for c in (_clause(k, req) for k in kinds) if c]

        if not clauses:
            # Last resort: restate the headline plus the freshest evidence row.
            if req.evidence:
                row = req.evidence[0]
                return f"{req.headline}. {row.label}: {row.value} (source: {row.source})."
            return req.headline

        return " ".join(clauses[:3])

    async def check_thesis(self, req: ThesisRequest) -> dict:
        """Lexical contradiction check — the honest non-LLM version.

        It looks for a stated *direction* in the thesis ("recovery", "margin
        expansion", "under 240") and compares it against the direction of the
        evidence. This is genuinely weaker than a language model at reading
        "hedge for my HDFC position", and it says so by returning NEUTRAL with
        low confidence rather than guessing — the design's own rule is that
        NEUTRAL is the correct and common answer.
        """
        thesis = req.exemplar_thesis.lower()
        blob = " ".join(f"{r.label} {r.value}".lower() for r in req.evidence)

        improving = ("recovery", "recover", "improve", "improving", "expansion",
                     "growth", "turnaround", "margin recovery", "rerating")
        deteriorating = ("down", "-", "fell", "decline", "miss", "below", "cut",
                         "contract", "warranty", "provision")

        wants_improvement = any(w in thesis for w in improving)
        evidence_deteriorating = any(w in blob for w in deteriorating)

        # "want it under 240" style: a price level the user is waiting for.
        level = None
        for token in thesis.replace("under", " ").replace("below", " ").split():
            cleaned = token.strip("₹rs.,")
            if cleaned.replace(".", "").isdigit():
                level = float(cleaned)
                break

        if wants_improvement and evidence_deteriorating:
            return {
                "verdict": "CONTRADICTS",
                "confidence": 0.62,
                "rationale": (
                    "The stated reason for watching describes an improvement. "
                    + " ".join(f"{r.label} was {r.value}." for r in req.evidence[:2])
                    + " That evidence points the other way."
                ),
            }

        if level is not None:
            return {
                "verdict": "NEUTRAL",
                "confidence": 0.30,
                "rationale": (
                    "The stated reason is a price level rather than a claim about "
                    "the business, so this evidence neither confirms nor contradicts it."
                ),
            }

        return {
            "verdict": "NEUTRAL",
            "confidence": 0.25,
            "rationale": (
                "The evidence does not bear directly on the stated reason for watching."
            ),
        }

    def snapshot(self) -> dict:
        return {"name": self.name, "state": "OK", "daily_cap": 0, "resets_at": None}


def parse_verdict(raw: str) -> dict | None:
    """Tolerant JSON extraction for the LLM providers' thesis responses.

    Free-tier models wrap JSON in prose and code fences with enthusiasm, so we
    find the first balanced object rather than trusting the response shape.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text[3:]
        text = text.removeprefix("json").strip()

    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
                if not isinstance(parsed, dict):
                    return None
                verdict = str(parsed.get("verdict", "NEUTRAL")).upper()
                if verdict not in ("CONTRADICTS", "SUPPORTS", "NEUTRAL"):
                    verdict = "NEUTRAL"
                try:
                    confidence = float(parsed.get("confidence", 0.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                return {
                    "verdict": verdict,
                    "confidence": max(0.0, min(1.0, confidence)),
                    "rationale": str(parsed.get("rationale", "")).strip(),
                }
    return None
