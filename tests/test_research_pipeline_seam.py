"""Tests für die Pipeline-Naht (d-lite): Research-Artefakte landen im geteilten Store,
sodass der math-research-Zweig vom Rest von GENESIS erreichbar ist (keine Insel)."""

from gen.identity_research import (
    AssumptionManifest,
    persist_identity_artifact,
    run_identity_research,
    assess_identity,
)
from gen.wissensbasis.store import list_fragments, load_fragment


def _mR():
    return AssumptionManifest(domain_id="R", variables={"x": "real"})


def test_run_identity_research_persists_to_shared_store():
    art, key = run_identity_research("pipe_pyth", "sin(x)**2 + cos(x)**2", "1", _mR())
    assert art.status == "SURVIVED_NOVEL"
    assert key is not None and key in list_fragments()
    rec = load_fragment(key)
    assert rec is not None
    assert "SURVIVED_NOVEL" in str(rec)        # honest status round-trips into the store
    assert "IdentityArtifact" in str(rec)


def test_persist_is_optional():
    art, key = run_identity_research("pipe_nopersist", "x + 1", "1 + x", _mR(), persist=False)
    assert art.status == "SURVIVED_NOVEL"
    assert key is None


def test_refuted_artifact_also_persists_with_witness():
    art = assess_identity("pipe_false", "x", "x + 1", _mR())
    key = persist_identity_artifact(art)
    assert key in list_fragments()
    rec = load_fragment(key)
    assert "REFUTED" in str(rec)
    # the disproof witness is preserved as a durable negative result
    assert "witness" in str(rec).lower()
