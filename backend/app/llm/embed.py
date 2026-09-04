"""Thesis embeddings.

DESIGN.md §7 specifies Voyage AI's finance-domain models in production. Voyage
has no free tier, and this prototype is free-tier-only, so what ships is a local
deterministic embedding with a documented ceiling.

**Hashed character n-grams into a fixed-dimension vector, L2 normalised.**
Sometimes called the hashing trick; it is what you use when you need cosine
similarity over short strings, no model download, no network, and no
dependencies. Properties:

*   Deterministic and stable across processes, so a thesis embedded today
    clusters with one embedded next month.
*   Genuinely good at the thing we need most: "watching for margin recovery"
    and "watching margins recover" land in the same cluster.
*   Genuinely bad at what it cannot do: it is lexical, not semantic. "waiting
    for a turnaround" and "watching for margin recovery" are the same belief to
    a human and to Voyage, and different beliefs to this. Character n-grams
    catch morphology and typos, not synonymy.

The consequence is bounded and acceptable: a missed cluster merge means we
generate one extra contradiction check per symbol, not a wrong answer. Cost
grows slightly; correctness does not move. And because it sits behind
`embed()`, swapping in Voyage or a local sentence-transformer is a one-function
change — `SentenceTransformerEmbedder` below is the drop-in if the optional
dependency happens to be installed.
"""

from __future__ import annotations

import hashlib
import logging
import re

import numpy as np

log = logging.getLogger("watchlist.llm.embed")

DIM = 256
NGRAM_SIZES = (3, 4, 5)

_WORD = re.compile(r"[a-z0-9]+")

# Words that carry no belief content. Dropped before hashing so "watching for
# margin recovery" and "margin recovery" cluster together.
STOPWORDS = frozenset(
    """a an the i is am are was were be been being my me mine to for of on in at
    it its this that these those and or but if then so as with about into over
    want wants wanted watch watching watched keep keeping looking look see
    seeing hoping hope waiting wait""".split()
)


def normalise(text: str) -> str:
    tokens = [t for t in _WORD.findall(text.lower()) if t not in STOPWORDS]
    return " ".join(tokens)


def _hash_index(token: str) -> int:
    digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % DIM


def embed(text: str, dim: int = DIM) -> list[float]:
    """Deterministic unit vector for a thesis string."""
    cleaned = normalise(text)
    vector = np.zeros(dim, dtype=float)
    if not cleaned:
        return vector.tolist()

    # Whole words carry the most signal, so they get extra weight over the
    # character n-grams that give us typo and morphology tolerance.
    for word in cleaned.split():
        vector[_hash_index(f"w:{word}")] += 2.0

    padded = f" {cleaned} "
    for n in NGRAM_SIZES:
        for i in range(len(padded) - n + 1):
            vector[_hash_index(padded[i : i + n])] += 1.0

    norm = float(np.linalg.norm(vector))
    if norm < 1e-12:
        return vector.tolist()
    return (vector / norm).tolist()


def cosine(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if x.size == 0 or y.size == 0 or x.size != y.size:
        return 0.0
    nx, ny = float(np.linalg.norm(x)), float(np.linalg.norm(y))
    if nx < 1e-12 or ny < 1e-12:
        return 0.0
    return float(np.clip(np.dot(x, y) / (nx * ny), -1.0, 1.0))


class SentenceTransformerEmbedder:
    """Optional upgrade path. Used automatically if the package is present.

    Not in requirements.txt on purpose: `sentence-transformers` pulls torch,
    which is a ~2GB download. A reviewer running `pip install -r
    requirements.txt` should not wait for that to see a watchlist, and the
    hashed fallback is good enough that blocking on it would be the wrong
    trade. DESIGN.md's instruction was explicitly not to block on this.
    """

    model_name = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self) -> None:
        self._model = None

    @property
    def available(self) -> bool:
        try:
            import sentence_transformers  # noqa: F401
        except ImportError:
            return False
        return True

    def embed(self, text: str) -> list[float]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            log.info("using %s for thesis embeddings", self.model_name)
        vec = self._model.encode(text, normalize_embeddings=True)
        return [float(v) for v in vec]


_upgraded: SentenceTransformerEmbedder | None = None


def best_embed(text: str) -> list[float]:
    """Use a real sentence encoder if one happens to be installed, else hash."""
    global _upgraded
    if _upgraded is None:
        _upgraded = SentenceTransformerEmbedder()
    if _upgraded.available:
        try:
            return _upgraded.embed(text)
        except Exception:  # pragma: no cover
            log.warning("sentence-transformers failed; using the hashed fallback")
    return embed(text)


def backend_name() -> str:
    global _upgraded
    if _upgraded is None:
        _upgraded = SentenceTransformerEmbedder()
    return (
        SentenceTransformerEmbedder.model_name
        if _upgraded.available
        else f"hashed-ngram-{DIM}d"
    )
