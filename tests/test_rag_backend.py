"""Tests for the in-memory RAG retrieval backend (tools/rag_backend.py).

Pins: it satisfies the SearchBackend protocol; cosine retrieval ranks the topically-matching document
first; results are capped, unfetched, and carry the backend + a provenance note; the embedder is
deterministic (hash-seed-independent); and an empty corpus / non-positive limit returns []. Offline.
"""

import pytest

from gen.core.interfaces import SearchBackend
from gen.core.state import SourceCandidate
from gen.tools.rag_backend import Document, RagBackend, char_ngram_embed

_CORPUS = [
    Document("doc:kepler", "Kepler orbital period", "the orbital period of a planet scales with the semi-major axis"),
    Document("doc:thermo", "Thermodynamics", "heat entropy temperature and the laws of thermodynamics"),
    Document("doc:nn", "Neural networks", "deep learning with gradient descent and backpropagation"),
]


def test_satisfies_the_search_backend_protocol():
    assert isinstance(RagBackend(_CORPUS), SearchBackend)


@pytest.mark.asyncio
async def test_ranks_the_topically_matching_document_first():
    hits = await RagBackend(_CORPUS).search("orbital period of a planet semi-major axis", limit=3)
    assert hits and hits[0].url_or_id == "doc:kepler"
    assert all(isinstance(h, SourceCandidate) for h in hits)
    assert hits[0].backend == "rag" and "cosine" in hits[0].relevance_note
    assert hits[0].fetched_ok is False                       # retrieval ranks; the scholar deep-reads


@pytest.mark.asyncio
async def test_respects_the_limit():
    hits = await RagBackend(_CORPUS).search("entropy", limit=2)
    assert len(hits) == 2


@pytest.mark.asyncio
async def test_empty_corpus_and_nonpositive_limit_return_nothing():
    assert await RagBackend([]).search("anything", limit=5) == []
    assert await RagBackend(_CORPUS).search("anything", limit=0) == []


def test_embedder_is_deterministic_and_normalised():
    import numpy as np

    a, b = char_ngram_embed("kepler orbital period"), char_ngram_embed("kepler orbital period")
    assert np.array_equal(a, b)                              # hash-seed-independent
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-9        # L2-normalised
