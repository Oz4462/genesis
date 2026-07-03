"""Tests für den Side-Channel-Research-Hook (Stein 1).

Default-off Integration: läuft strukturierte Proposals async ab, schreibt ehrliche
Log-Zeilen, und fasst NIEMALS state.claims an (SURVIVED_* != VERIFIED).
"""

import asyncio

from gen.core.state import Question, RunState
from gen.identity_research import AssumptionManifest, NoveltyIndex
from gen.integration.identity_research_hook import (
    IdentityProposal,
    enrich_run_with_identity_research,
)


def _state():
    return RunState(question=Question(raw="math-research side channel", run_id="hook-test"))


def _mR():
    return AssumptionManifest(domain_id="R", variables={"x": "real"})


def test_hook_assesses_proposals_and_logs_without_touching_claims():
    state = _state()
    proposals = [
        IdentityProposal("pyth", "sin(x)**2 + cos(x)**2", "1", _mR()),
        IdentityProposal("false1", "x", "x + 1", _mR()),
        IdentityProposal("ineq", "x**2", "0", _mR(), relation="ge"),
    ]
    arts = asyncio.run(enrich_run_with_identity_research(state, proposals, novelty_index=NoveltyIndex(), persist=False))
    assert [a.status for a in arts] == ["SURVIVED_NOVEL", "REFUTED", "SURVIVED_NOVEL"]
    # honest log lines were appended
    assert sum(1 for line in state.log if line.startswith("identity_research:")) == 3
    # the side channel never elevates claims
    assert state.claims == []


def test_hook_no_proposals_is_noop():
    state = _state()
    arts = asyncio.run(enrich_run_with_identity_research(state, [], persist=False))
    assert arts == []
    assert state.log == []


def test_hook_refuted_proposal_carries_witness():
    state = _state()
    arts = asyncio.run(enrich_run_with_identity_research(
        state, [IdentityProposal("f", "x", "x + 1", _mR())], persist=False))
    assert arts[0].status == "REFUTED"
    assert arts[0].falsify.witness is not None
