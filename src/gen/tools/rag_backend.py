"""rag_backend — an in-memory cosine retrieval SearchBackend (RAG / PaperQA adoption, offline core).

The knowledge axis: literature-grounded discovery needs RETRIEVAL — embed a query, find the most similar
documents, and surface them as candidate sources whose provenance flows into the ledger (CLAUDE.md §1:
no fact without a source). This is that retrieval backend, satisfying the existing ``SearchBackend``
protocol so it drops into the scout/scholar pipeline beside the arXiv backend.

It is fully offline by default: a deterministic character-n-gram embedder (a stable, hash-seed-
independent bag of 3-grams, L2-normalised) means cosine retrieval is reproducible with no model and no
network. A real dense embedder + pgvector store is opt-in — inject a different ``embedder`` callable and
the same cosine search runs over learned vectors (the PaperQA2 pattern: dense top-k, then the scholar
deep-reads and only THEN does anything become a Claim). Returned candidates are UNFETCHED — retrieval
ranks, the scholar disposes. numpy-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from ..core.state import SourceCandidate


def _stable_hash(text: str) -> int:
    """A deterministic polynomial hash (independent of PYTHONHASHSEED, unlike ``hash()``)."""
    value = 0
    for char in text:
        value = (value * 131 + ord(char)) & 0xFFFFFFFF
    return value


def char_ngram_embed(text: str, *, dim: int = 512, n: int = 3) -> np.ndarray:
    """A deterministic bag-of-character-n-grams vector, L2-normalised — the offline default embedder."""
    vector = np.zeros(dim, dtype=float)
    lowered = text.lower()
    if len(lowered) < n:
        lowered = lowered.ljust(n)
    for i in range(len(lowered) - n + 1):
        vector[_stable_hash(lowered[i : i + n]) % dim] += 1.0
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm > 0.0 else vector


@dataclass(frozen=True)
class Document:
    """A corpus document: a stable id/url, a title, and the text to embed."""

    url_or_id: str
    title: str
    text: str


class RagBackend:
    """Cosine retrieval over an in-memory corpus, satisfying the ``SearchBackend`` protocol."""

    name = "rag"

    def __init__(
        self,
        corpus: Sequence[Document],
        *,
        embedder: Callable[[str], np.ndarray] = char_ngram_embed,
    ) -> None:
        self._corpus = list(corpus)
        self._embed = embedder
        # precompute one vector per document (title + text), so search is a single matmul.
        self._vectors = [embedder(f"{doc.title} {doc.text}") for doc in self._corpus]

    async def search(self, query: str, limit: int) -> list[SourceCandidate]:
        """Return the ``limit`` most cosine-similar documents as UNFETCHED source candidates, each with
        its similarity recorded in the relevance note (provenance for the ledger)."""
        if not self._corpus or limit <= 0:
            return []
        query_vector = self._embed(query)
        scored = sorted(
            (
                (float(np.dot(query_vector, vector)), doc)
                for vector, doc in zip(self._vectors, self._corpus)
            ),
            key=lambda pair: (-pair[0], pair[1].url_or_id),
        )
        return [
            SourceCandidate(
                url_or_id=doc.url_or_id,
                title=doc.title,
                backend=self.name,
                relevance_note=f"cosine {score:.3f} (RAG, deep-read before any claim)",
            )
            for score, doc in scored[:limit]
        ]
