"""Qdrant ledger backend — semantic recall against a live Qdrant server.

``ledger/qdrant.py`` offers the SAME injected-embedder recall seam as the pgvector
adapter, backed by Qdrant instead. These tests pin, against a real server:

  * POSITIVE: store provenance-backed Claims, then recall by query — the most
    semantically similar claim ranks first, AND its full provenance (sources,
    verification, status, confidence) round-trips out of the point payload exactly
    as a relational ``get_claims`` would return it;
  * NEGATIVE (cross-model isolation): a query under a DIFFERENT ``embed_model`` recalls
    nothing — vectors from different embedders are never silently compared;
  * NEGATIVE (loud failure): a query/store vector of the wrong dimension raises the
    typed ``GenesisError`` (no silent cross-space comparison); a dimension-mismatched
    existing collection is rejected; storing a sourceless claim is impossible.

Two FAST unit tests (no server, always run): an unconnected store fails loud, and a
sourceless claim cannot be stored. The server-dependent tests SKIP when ``qdrant-client``
is absent or no server answers on the configured URL (the ``_integration`` suffix marks
them slow/server-dependent).

Engine: Qdrant (localhost:6333 by default). Run:  pytest tests/test_qdrant_ledger_integration.py
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import GenesisError, UnsourcedClaimError  # noqa: E402
from gen.core.state import Claim, ClaimStatus, SourceRef, SourceSupport  # noqa: E402
from gen.ledger.qdrant import (  # noqa: E402
    QdrantConfig,
    QdrantLedgerStore,
    qdrant_available,
)


# --- a tiny deterministic 4-D embedder (keyword-indicator vector) ------------------

def _toy_embedder(text: str) -> list[float]:
    """A deterministic 4-D vector keyed on keyword presence — enough to make
    'steel/yield' queries land on the steel claim and not the aluminum one."""
    t = text.lower()
    return [
        1.0 if "steel" in t else 0.0,
        1.0 if "yield" in t else 0.0,
        1.0 if "aluminum" in t else 0.0,
        1.0 if "density" in t else 0.0,
    ]


def _steel_claim() -> Claim:
    return Claim(
        id="c_steel",
        text="steel yield strength is about 250 MPa",
        sources=[SourceRef("matweb.com/steel", True, support=SourceSupport.SUPPORTS)],
        quote="yield strength 250 MPa",
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
        verification=[SourceRef("nist.gov/steel", True, support=SourceSupport.SUPPORTS)],
        produced_by="scholar",
        model="qwen",
    )


def _aluminum_claim() -> Claim:
    return Claim(
        id="c_alu",
        text="aluminum density is 2700 kg/m3",
        sources=[SourceRef("engtoolbox/alu", True, support=SourceSupport.SUPPORTS)],
    )


# --- FAST unit tests (no server) ---------------------------------------------------

def test_unconnected_store_is_loud():
    """Recalling/storing before connect() raises GenesisError — never a silent no-op."""
    store = QdrantLedgerStore(config=QdrantConfig.from_env())
    with pytest.raises(GenesisError):
        store.recall_similar("x", _toy_embedder, embed_model="toy")


def test_sourceless_claim_cannot_be_constructed():
    """A sourceless Claim cannot even be built — the store never gets the chance to
    persist a fact without provenance (CLAUDE.md §1)."""
    with pytest.raises(UnsourcedClaimError):
        Claim(id="c_bad", text="unbacked assertion", sources=[])


# --- server-dependent integration tests --------------------------------------------

_HAVE_CLIENT = qdrant_available()


def _server_up() -> bool:
    if not _HAVE_CLIENT:
        return False
    try:
        store = QdrantLedgerStore(config=QdrantConfig.from_env())
        store.connect()
        store._require_client().get_collections()  # noqa: SLF001 - probe
        store.close()
        return True
    except Exception:
        return False


_skip_no_server = pytest.mark.skipif(
    not _server_up(), reason="qdrant-client missing or no Qdrant server on the configured URL"
)


@pytest.fixture()
def store():
    """A connected store on a throwaway 4-D collection (created fresh, dropped after)."""
    name = f"genesis_test_{uuid.uuid4().hex[:12]}"
    cfg = QdrantConfig(
        url=None, host="localhost", port=6333, collection=name, embed_dim=4
    )
    s = QdrantLedgerStore(config=cfg)
    s.connect()
    try:
        s._client.delete_collection(name)  # noqa: SLF001
    except Exception:
        pass
    s.ensure_collection()
    try:
        yield s
    finally:
        try:
            s._client.delete_collection(name)  # noqa: SLF001
        finally:
            s.close()


@_skip_no_server
def test_recall_ranks_semantically_and_round_trips_provenance(store):
    store.store_embedding(_steel_claim(), _toy_embedder, embed_model="toy4")
    store.store_embedding(_aluminum_claim(), _toy_embedder, embed_model="toy4")

    res = store.recall_similar(
        "what is the yield strength of steel", _toy_embedder, embed_model="toy4", limit=2
    )
    assert res, "recall returned nothing"
    top_claim, top_sim = res[0]
    # the steel claim is the closest (query has steel+yield, not aluminum/density)
    assert top_claim.id == "c_steel", [c.id for c, _ in res]
    assert top_sim > 0.7
    # full provenance reconstructed from the payload (not lost in the vector store)
    assert top_claim.sources[0].url_or_id == "matweb.com/steel"
    assert top_claim.sources[0].support is SourceSupport.SUPPORTS
    assert top_claim.verification[0].url_or_id == "nist.gov/steel"
    assert top_claim.status is ClaimStatus.VERIFIED
    assert top_claim.confidence == pytest.approx(0.9)
    assert top_claim.produced_by == "scholar" and top_claim.model == "qwen"


@_skip_no_server
def test_cross_model_vectors_are_never_compared(store):
    """A query under a different embed_model recalls nothing — no apples-to-oranges
    similarity across embedding spaces (the one thing recall must never get wrong)."""
    store.store_embedding(_steel_claim(), _toy_embedder, embed_model="toy4")
    res = store.recall_similar("steel", _toy_embedder, embed_model="OTHER_MODEL", limit=5)
    assert res == []


@_skip_no_server
def test_restore_is_idempotent(store):
    """Re-storing the same (claim, model) upserts the same point — no duplicates."""
    store.store_embedding(_steel_claim(), _toy_embedder, embed_model="toy4")
    store.store_embedding(_steel_claim(), _toy_embedder, embed_model="toy4")
    res = store.recall_similar("steel yield", _toy_embedder, embed_model="toy4", limit=10)
    assert [c.id for c, _ in res] == ["c_steel"]


@_skip_no_server
def test_wrong_query_dimension_is_loud(store):
    """A query embedding of the wrong length raises GenesisError before touching the
    server — never a silent comparison across dimensions."""
    store.store_embedding(_steel_claim(), _toy_embedder, embed_model="toy4")
    with pytest.raises(GenesisError):
        store.recall_similar("x", lambda t: [1.0, 2.0, 3.0], embed_model="toy4")


@_skip_no_server
def test_dimension_mismatch_on_existing_collection_is_loud(store):
    """A store configured for a different dimension than an existing collection refuses
    to use it (a silent mismatch would corrupt every later similarity query)."""
    other = QdrantLedgerStore(
        config=QdrantConfig(
            url=None, host="localhost", port=6333, collection=store.collection, embed_dim=8
        )
    )
    other.connect()
    try:
        with pytest.raises(GenesisError):
            other.ensure_collection()
    finally:
        other.close()
