"""The provider interface, and the request shape every provider is handed.

DESIGN.md §7 argues for `claude-opus-5` in production on cost and quality
grounds, with the whole $200/month table computed against Anthropic pricing.
This prototype runs **free tiers only** — a hard requirement — so what ships is
Gemini and OpenRouter behind this protocol, with a deterministic template as the
floor.

The protocol is the point. Swapping in Anthropic is one file implementing three
methods and one line in the router's cascade; nothing about the caching, the
per-symbol-event fan-in, the quota accounting or the compliance filter changes.
That is the difference between "we used a free tier" and "we designed for a
free tier and can leave it".

`SummaryRequest` carries **evidence rows, never raw prices**. A provider is
physically not given anything it could editorialise about, because
contracts/API.md requires every claim in a summary to be traceable to
`signals[].evidence[]`. If it is not in the evidence, the model cannot have
seen it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class EvidenceRow:
    label: str
    value: str
    as_of: str
    source: str


@dataclass(frozen=True)
class SummaryRequest:
    """Everything a summariser is allowed to know about a symbol-event.

    One of these exists per symbol-event, not per user. That is the entire
    economic argument in DESIGN.md §7: 10k users checking in produce ~200,000
    naive calls/day, while summarising each symbol-event once produces ~300.
    Marginal cost per additional subscriber is zero because there is no
    per-user field in this struct to vary.
    """

    symbol: str
    name: str
    event_id: str
    headline: str
    signal_kinds: tuple[str, ...]
    evidence: tuple[EvidenceRow, ...]
    change_pct: float
    idiosyncratic_pct: float | None
    as_of: str

    def content_hash(self) -> str:
        """Stable hash of everything that could change the output.

        Deliberately excludes `event_id` and any timestamp that is not part of
        the evidence, so two events with identical evidence share a cache entry.
        Identical inputs must never re-call a provider.
        """
        canonical = json.dumps(
            {
                "symbol": self.symbol,
                "headline": self.headline,
                "kinds": sorted(self.signal_kinds),
                "evidence": sorted(
                    [[e.label, e.value, e.source] for e in self.evidence]
                ),
                "change_pct": round(self.change_pct, 2),
                "idio": None
                if self.idiosyncratic_pct is None
                else round(self.idiosyncratic_pct, 2),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:32]


@dataclass(frozen=True)
class ThesisRequest:
    """A contradiction check against one *belief cluster*, not one user.

    `cluster_id` and `exemplar_thesis` stand in for every user who wrote
    semantically the same thing. See llm/thesis.py.
    """

    symbol: str
    name: str
    event_id: str
    cluster_id: str
    exemplar_thesis: str
    headline: str
    evidence: tuple[EvidenceRow, ...]

    def content_hash(self) -> str:
        canonical = json.dumps(
            {
                "symbol": self.symbol,
                "cluster": self.cluster_id,
                "thesis": self.exemplar_thesis.strip().lower(),
                "evidence": sorted([[e.label, e.value] for e in self.evidence]),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:32]


@dataclass
class Completion:
    text: str
    provider: str
    cached: bool = False
    latency_ms: float = 0.0
    meta: dict = field(default_factory=dict)


class ProviderError(Exception):
    """Base for provider failures. `retryable` drives the backoff decision."""

    retryable = True


class RateLimited(ProviderError):
    """429 or a locally-enforced token-bucket refusal."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class QuotaExhausted(ProviderError):
    """Daily cap reached. Not retryable until it resets."""

    retryable = False

    def __init__(self, message: str, resets_at: datetime | None = None,
                 observed_cap: int | None = None) -> None:
        super().__init__(message)
        self.resets_at = resets_at
        # Free-tier quotas move without notice, so when a provider tells us what
        # the real cap was, we believe it over our configured guess.
        self.observed_cap = observed_cap


class ProviderUnavailable(ProviderError):
    """Network error, 5xx, or no API key configured."""


@runtime_checkable
class Provider(Protocol):
    name: str

    @property
    def configured(self) -> bool:
        """False when no API key is present. An unconfigured provider is
        skipped by the cascade rather than counted as a failure — a missing key
        is a deployment choice, not an outage."""
        ...

    async def summarise(self, req: SummaryRequest) -> str: ...

    async def check_thesis(self, req: ThesisRequest) -> dict: ...
