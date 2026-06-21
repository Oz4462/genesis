"""Phase χ acceptance — the frontier map (HORIZON.md §2C). Gate-first, deterministic, LLM-free.

Teeth: a known region without an anchor is impossible (constructor); GATE χ rejects an
unverified 'known' fact and an invented frontier edge (one not grounded in a real gap);
the deterministic builder produces a gate-passing map; abstention is valid.
"""

from __future__ import annotations

import pytest

from gen.core.errors import UnknownRegionError
from gen.core.state import (
    Claim,
    ClaimStatus,
    FrontierEdge,
    FrontierMap,
    KnownRegion,
    Question,
    Report,
    RunState,
    SourceRef,
)
from gen.frontier import build_frontier_map
from gen.verification import gate_chi


def _verified(cid: str = "c_v", conf: float = 0.9) -> Claim:
    return Claim(id=cid, text=f"Verified fact {cid}.",
                 sources=[SourceRef(url_or_id=f"s://{cid}", retrieved=True)],
                 status=ClaimStatus.VERIFIED, confidence=conf)


def _unsupported(cid: str = "c_u") -> Claim:
    return Claim(id=cid, text=f"Unsupported {cid}.",
                 sources=[SourceRef(url_or_id=f"s://{cid}", retrieved=True)],
                 status=ClaimStatus.UNSUPPORTED, confidence=0.0)


def _state(claims):
    return RunState(question=Question(raw="topic", run_id="x1"), claims=list(claims))


# --- data-model teeth ---------------------------------------------------------
def test_known_region_without_anchor_is_impossible():
    with pytest.raises(UnknownRegionError):
        KnownRegion(id="r0", label="empty", fact_ids=[])


# --- GATE χ -------------------------------------------------------------------
def test_known_must_be_verified():
    st = _state([_unsupported("c_u")])
    fmap = FrontierMap(run_id="x1", topic="t",
                       known_regions=[KnownRegion(id="r0", label="x", fact_ids=["c_u"])])
    res = gate_chi(st, fmap)
    assert not res.passed and any(f.code == "KNOWN_UNVERIFIED" for f in res.failures)


def test_known_unknown_claim_fails():
    fmap = FrontierMap(run_id="x1", topic="t",
                       known_regions=[KnownRegion(id="r0", label="x", fact_ids=["c_missing"])])
    res = gate_chi(_state([_verified()]), fmap)
    assert not res.passed and any(f.code == "KNOWN_UNKNOWN_CLAIM" for f in res.failures)


def test_invented_frontier_edge_fails():
    # edge grounds in something that is NOT a real gap of the run -> rejected
    fmap = FrontierMap(run_id="x1", topic="t",
                       frontier_edges=[FrontierEdge(id="e0", question="erfunden?",
                                                    grounded_in="nicht-existent")])
    res = gate_chi(_state([_verified()]), fmap)
    assert not res.passed and any(f.code == "FRONTIER_NOT_GROUNDED" for f in res.failures)


def test_edge_grounded_in_real_gap_passes():
    st = _state([_verified()])
    st.report = Report(run_id="x1", question="t", body="b", gaps=["offene Frage X"])
    fmap = FrontierMap(run_id="x1", topic="t",
                       frontier_edges=[FrontierEdge(id="e0", question="offene Frage X",
                                                    grounded_in="offene Frage X")])
    assert gate_chi(st, fmap).passed


def test_abstention_passes():
    # no known regions, one edge grounded in an UNSUPPORTED claim -> honest open map
    st = _state([_unsupported("c_u")])
    fmap = FrontierMap(run_id="x1", topic="t",
                       frontier_edges=[FrontierEdge(id="e0", question="Unsupported c_u.",
                                                    grounded_in="c_u")])
    assert gate_chi(st, fmap).passed


def test_empty_edge_is_impossible():
    # adversarial-review finding: an empty/whitespace gap must not become a valid edge
    with pytest.raises(ValueError):
        FrontierEdge(id="e0", question="", grounded_in="")
    with pytest.raises(ValueError):
        FrontierEdge(id="e1", question="q", grounded_in="   ")


def test_builder_skips_empty_gaps():
    st = _state([_verified("c_v")])
    st.report = Report(run_id="x1", question="t", body="b",
                       statement_to_claim={}, gaps=["", "   ", "echte Lücke"])
    fmap = build_frontier_map(st)
    grounds = [e.grounded_in for e in fmap.frontier_edges]
    assert grounds == ["echte Lücke"]  # empty/whitespace gaps dropped, real one kept
    assert gate_chi(st, fmap).passed


# --- deterministic builder ----------------------------------------------------
def test_builder_produces_gate_passing_map():
    cv, cu = _verified("c_v"), _unsupported("c_u")
    st = _state([cv, cu])
    st.report = Report(run_id="x1", question="t", body="b",
                       statement_to_claim={cv.text: cv.id}, gaps=["offene Frage X"])
    fmap = build_frontier_map(st)
    assert gate_chi(st, fmap).passed
    assert len(fmap.known_regions) == 1 and fmap.known_regions[0].fact_ids == ["c_v"]
    grounds = {e.grounded_in for e in fmap.frontier_edges}
    assert "offene Frage X" in grounds and "c_u" in grounds  # gap + unsupported surfaced
    # deterministic content: same state -> identical map (created_at is metadata, like Claim)
    again = build_frontier_map(st)
    assert (again.run_id, again.topic, again.known_regions, again.frontier_edges) == (
        fmap.run_id, fmap.topic, fmap.known_regions, fmap.frontier_edges
    )
