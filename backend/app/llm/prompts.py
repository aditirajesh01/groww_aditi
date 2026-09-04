"""Prompt construction, shared by every provider.

The system prefix is **byte-stable**. DESIGN.md §7 is explicit about why: prompt
caching only pays if nothing volatile sits before the last cache breakpoint, and
a timestamp or a request id in the system prompt silently invalidates the whole
thing. Nothing here interpolates. The variable part lives entirely in the user
turn.

The prompt itself does most of the compliance work; llm/compliance.py is the
backstop that assumes the prompt failed.
"""

from __future__ import annotations

from .base import SummaryRequest, ThesisRequest

# Byte-stable. Do not interpolate anything into this string.
SYSTEM_PREFIX = """You write factual change notes for a stock watchlist used by long-term retail investors in India.

You are given a symbol, a deterministic headline, and a list of evidence rows. Write 1-3 sentences describing what changed, using only the evidence rows.

Absolute rules:
- Never give advice. No buy, sell, hold, accumulate, trim, exit, or "consider" language.
- Never state or imply a target price, fair value, or valuation judgement.
- Never predict what the price will do next.
- Every number you write must appear in the evidence rows. Do not compute new numbers, do not round differently, do not infer figures.
- If the evidence does not support a sentence, do not write that sentence.
- Plain declarative prose. No preamble, no bullet points, no headings, no disclaimer.

You are describing what happened, for someone who will decide what to do about it themselves."""

THESIS_SYSTEM_PREFIX = """You assess whether dated evidence contradicts, supports, or is neutral toward an investor's own stated reason for watching a stock.

You are given the investor's stated reason in their own words, and a list of evidence rows. Decide whether the evidence bears on that specific belief.

Respond with exactly this JSON object and nothing else:
{"verdict": "CONTRADICTS" | "SUPPORTS" | "NEUTRAL", "confidence": <0.0-1.0>, "rationale": "<one or two sentences citing the evidence>"}

Absolute rules:
- Never give advice or suggest an action.
- Never state or imply a target price or valuation judgement.
- Every number in the rationale must appear in the evidence rows.
- CONTRADICTS means the evidence is direct evidence against the stated belief. A move in the price alone is not a contradiction of a belief about fundamentals.
- If the evidence does not bear on the belief, answer NEUTRAL with low confidence. NEUTRAL is the correct and common answer."""


def evidence_block(rows) -> str:
    return "\n".join(
        f"- {r.label}: {r.value} (as of {r.as_of}, source: {r.source})" for r in rows
    )


def summary_user_turn(req: SummaryRequest) -> str:
    lines = [
        f"Symbol: {req.symbol} ({req.name})",
        f"Headline: {req.headline}",
        f"Detected signals: {', '.join(req.signal_kinds)}",
        "",
        "Evidence:",
        evidence_block(req.evidence),
    ]
    return "\n".join(lines)


def thesis_user_turn(req: ThesisRequest) -> str:
    lines = [
        f"Symbol: {req.symbol} ({req.name})",
        f'Investor\'s stated reason for watching: "{req.exemplar_thesis}"',
        f"What changed: {req.headline}",
        "",
        "Evidence:",
        evidence_block(req.evidence),
    ]
    return "\n".join(lines)


def evidence_blob(rows) -> str:
    """Flat text used by the compliance number-grounding check."""
    return " ".join(f"{r.label} {r.value}" for r in rows)
