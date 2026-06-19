"""Integration: the offline RAG retrieval backend composes into the LIVE `Scout` pipeline.

This is the knowledge-axis wiring proof. `RagBackend` (cosine retrieval over an in-memory corpus)
satisfies the same `SearchBackend` protocol the scout already consumes, so it drops into the real
agent with NO production-code change — interface-first composition (CLAUDE.md §6: code against the
interfaces, not a framework). These tests run the REAL `Scout` over the REAL `RagBackend` (no fakes
for the unit under test) and pin:

  * a question flows through the scout into RAG retrieval, and RAG-sourced candidates (backend="rag")
    land in ``state.candidates`` — the axis is integrated, not just buildable;
  * ranking survives the seam: the most cosine-similar document surfaces FIRST (RagBackend sorts,
    Scout preserves order) — end-to-end correctness, not merely end-to-end flow;
  * RAG composes BESIDE a second backend (the arXiv slot) and the scout merges + dedupes both;
  * the scout's ``per_query_limit`` flows through to dense top-k (the PaperQA2 pattern);
  * retrieval creates ZERO claims — it ranks candidates, the scholar deep-reads and only THEN may a
    claim exist (no fact without a source; rag_backend: "deep-read before any claim").

Fully offline + deterministic (char-n-gram embedder, no network, no model): a re-run yields the
identical candidate order (GENESIS determinism principle #5).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.scout import Scout  # noqa: E402
from gen.core.state import Question, RunState, SourceCandidate  # noqa: E402
from gen.tools.rag_backend import Document, RagBackend  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def _corpus() -> list[Document]:
    # One document shares the query phrase verbatim (high char-3-gram overlap); the others are
    # unrelated, so the cosine ranking has a clear, hand-checkable winner.
    return [
        Document("doc:kepler", "Kepler third law",
                 "the orbital period of a planet grows with the size of its orbit"),
        Document("doc:thermo", "Thermodynamics",
                 "the entropy of an isolated system never decreases over time"),
        Document("doc:beam", "Cantilever beam",
                 "tip deflection of a beam under a transverse point load at its free end"),
    ]


def _state(raw: str) -> RunState:
    return RunState(question=Question(raw=raw, run_id="rag-int"))


def test_rag_backend_is_pluggable_into_the_live_scout():
    # The whole point: the real Scout consumes the real RagBackend with no adapter.
    scout = Scout([RagBackend(_corpus())])
    st = run(scout.run(_state("orbital period of a planet")))

    assert st.candidates, "RAG retrieval surfaced no candidates into the scout"
    assert all(c.backend == "rag" for c in st.candidates)        # every candidate came from RAG
    assert all(isinstance(c, SourceCandidate) for c in st.candidates)
    assert {c.url_or_id for c in st.candidates} == {"doc:kepler", "doc:thermo", "doc:beam"}


def test_ranking_survives_the_seam_most_similar_document_is_first():
    # RagBackend returns sorted by descending cosine; the Scout appends in backend order, so the
    # highest-similarity document must be the first candidate the pipeline sees.
    scout = Scout([RagBackend(_corpus())])
    st = run(scout.run(_state("orbital period of a planet")))
    assert st.candidates[0].url_or_id == "doc:kepler"
    assert "cosine" in st.candidates[0].relevance_note          # provenance flows for the ledger


def test_rag_composes_beside_a_second_backend_and_scout_merges_both():
    # The documented shape: RAG drops in BESIDE the arXiv backend. Both contribute; the scout
    # merges and dedupes. A minimal second backend stands in for arXiv.
    class FakeArxiv:
        name = "arxiv"

        async def search(self, query, limit):  # noqa: ARG002 - fixed-response fake ignores query
            return [SourceCandidate(url_or_id="arxiv:2401.00001", title="A paper",
                                    backend=self.name, relevance_note="match")][:limit]

    scout = Scout([RagBackend(_corpus()), FakeArxiv()])
    st = run(scout.run(_state("orbital period of a planet")))
    backends = {c.backend for c in st.candidates}
    assert backends == {"rag", "arxiv"}                         # both axes present in one run
    assert any(c.url_or_id == "arxiv:2401.00001" for c in st.candidates)


def test_per_query_limit_flows_through_to_dense_top_k():
    # The scout passes its per_query_limit to backend.search, so RAG returns only the top-k. With
    # limit=1 over a 3-doc corpus, only the single best match reaches the pipeline.
    scout = Scout([RagBackend(_corpus())], per_query_limit=1)
    st = run(scout.run(_state("orbital period of a planet")))
    assert [c.url_or_id for c in st.candidates] == ["doc:kepler"]


def test_retrieval_creates_no_claims():
    # Retrieval ranks; it never asserts a fact. The scholar deep-reads candidates and only THEN may
    # a Claim exist (no fact without a source).
    scout = Scout([RagBackend(_corpus())])
    st = run(scout.run(_state("orbital period of a planet")))
    assert st.claims == []


def test_composition_is_deterministic():
    scout = Scout([RagBackend(_corpus())])
    a = run(scout.run(_state("orbital period of a planet")))
    b = run(scout.run(_state("orbital period of a planet")))
    assert [c.url_or_id for c in a.candidates] == [c.url_or_id for c in b.candidates]
