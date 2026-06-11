"""Tests for the `architect` agent — structure without invention (PHASE_GAMMA §4).

Scripted LLM, no network. The contract under test: grounded values must literally
match a VERIFIED claim, derived values are computed by CODE (LLM math ignored),
hidden decisions are dropped, and a structurally defective proposal yields an
honest abstention — never a partial build plan.

Run:  pytest tests/test_architect.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Make src importable without packaging during early dev.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.agents.architect import Architect  # noqa: E402
from gen.core.state import (  # noqa: E402
    Approach,
    Claim,
    ClaimStatus,
    Question,
    RunState,
    SourceRef,
    SourceSupport,
    ValueOrigin,
)
from gen.llm.base import ScriptedLLM  # noqa: E402
from gen.verification.gates import gate_gamma  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def _src(url: str) -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=True, support=SourceSupport.SUPPORTS)


def _claim(cid: str, text: str) -> Claim:
    return Claim(
        id=cid,
        text=text,
        sources=[_src(f"https://example.org/{cid}")],
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
        verification=[_src(f"https://independent.org/{cid}")],
    )


def _state(*, with_approach: bool = True) -> RunState:
    st = RunState(question=Question(raw="wall-mounted shelf bracket", run_id="rg"))
    st.claims = [
        _claim("c1", "The shelf must carry a load of 12 kg."),
        _claim("c2", "Cantilever brackets are used for wall-mounted shelves."),
    ]
    if with_approach:
        st.approaches = [Approach(id="ap1", name="Cantilever bracket", grounding=["c2"])]
    return st


def _proposal(**overrides) -> dict:
    base = {
        "approach_id": "ap1",
        "quantities": [
            {"id": "q_load", "name": "load", "unit": "kg", "origin": "grounded",
             "value": 12, "grounding": ["c1"]},
            {"id": "q_sf", "name": "safety factor", "unit": "1", "origin": "decision",
             "value": 2, "rationale": "conservative; 1.5 and 3 considered"},
            # The LLM "precomputed" 999 — the code must ignore that and compute 24.
            {"id": "q_design", "name": "design load", "unit": "kg", "origin": "derived",
             "formula": "q_load * q_sf", "inputs": ["q_load", "q_sf"], "value": 999},
        ],
        "components": [
            {"id": "c_bracket", "name": "bracket", "quantity_ids": ["q_load"]},
        ],
        "bom": [
            {"id": "b_bracket", "name": "bracket", "role": "part", "count": 1,
             "component_id": "c_bracket"},
        ],
        "steps": [
            {"id": "s1", "index": 1, "action": "Mount the bracket to the wall.",
             "uses": ["b_bracket"], "inputs": ["b_bracket"], "outputs": ["a_done"],
             "check": "Bracket carries q_design without movement.",
             "quantity_refs": ["q_design"]},
        ],
        "constraints": [],
        "decisions": [
            {"id": "d_mat", "title": "Material", "choice": "PLA",
             "rationale": "locally available, sufficient for static indoor load"},
        ],
    }
    base.update(overrides)
    return base


def _architect_for(payload) -> Architect:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return Architect(ScriptedLLM("claude-opus-4-8", text))


# --- happy path ----------------------------------------------------------------

def test_assembles_specification_that_passes_gate_gamma():
    state = _state()
    run(_architect_for(_proposal()).run(state))
    spec = state.specification
    assert spec is not None and spec.approach_id == "ap1"
    assert {q.id for q in spec.quantities} == {"q_load", "q_sf", "q_design"}
    assert gate_gamma(state).passed


def test_llm_arithmetic_is_ignored_and_recomputed_by_code():
    state = _state()
    run(_architect_for(_proposal()).run(state))
    q_design = next(q for q in state.specification.quantities if q.id == "q_design")
    assert q_design.value == 24.0          # 12 * 2 — NOT the LLM's 999
    assert q_design.origin is ValueOrigin.DERIVED
    assert any("ignoring LLM-supplied value" in ln for ln in state.log)


# --- the fabricated-value trap ---------------------------------------------------

def test_fabricated_grounded_value_is_dropped_never_asserted():
    proposal = _proposal()
    proposal["quantities"].append(
        {"id": "q_fake", "name": "tensile strength", "unit": "MPa",
         "origin": "grounded", "value": 70, "grounding": ["c1"]}  # c1 says 12, not 70
    )
    state = _state()
    run(_architect_for(proposal).run(state))
    spec = state.specification
    assert spec is not None
    assert all(q.id != "q_fake" for q in spec.quantities)        # never asserted
    assert any("q_fake" in ln and "not found literally" in ln for ln in state.log)
    assert gate_gamma(state).passed                              # rest stays sound


def test_grounding_in_unknown_claim_is_dropped():
    proposal = _proposal()
    proposal["quantities"].append(
        {"id": "q_ghosted", "name": "x", "unit": "mm", "origin": "grounded",
         "value": 3, "grounding": ["ghost"]}
    )
    state = _state()
    run(_architect_for(proposal).run(state))
    assert all(q.id != "q_ghosted" for q in state.specification.quantities)


def test_hidden_decision_is_dropped():
    proposal = _proposal()
    proposal["quantities"].append(
        {"id": "q_sneaky", "name": "margin", "unit": "1", "origin": "decision",
         "value": 1.5}  # no rationale -> hidden decision
    )
    state = _state()
    run(_architect_for(proposal).run(state))
    assert all(q.id != "q_sneaky" for q in state.specification.quantities)


# --- abstention paths -------------------------------------------------------------

def test_no_grounded_approach_abstains():
    state = _state(with_approach=False)
    run(_architect_for(_proposal()).run(state))
    spec = state.specification
    assert spec is not None
    assert spec.components == [] and spec.steps == [] and spec.quantities == []
    assert spec.gaps                                            # named gap
    assert gate_gamma(state).passed                             # honest emptiness


def test_unparseable_llm_output_abstains():
    state = _state()
    run(_architect_for("this is not json at all").run(state))
    spec = state.specification
    assert spec is not None and spec.gaps and spec.components == []


def test_structurally_defective_proposal_abstains_instead_of_partial_spec():
    proposal = _proposal()
    proposal["steps"][0]["uses"] = ["b_ghost"]                  # dangling reference
    state = _state()
    run(_architect_for(proposal).run(state))
    spec = state.specification
    assert spec is not None
    assert spec.components == [] and spec.steps == []           # no partial plan
    assert any("structural defects" in g for g in spec.gaps)
    assert any("DANGLING_REFERENCE" in ln for ln in state.log)
    assert gate_gamma(state).passed                             # abstention is sound


def test_unknown_anchor_yields_abstention_not_reanchoring():
    proposal = _proposal(approach_id="ap_ghost")
    state = _state()
    run(_architect_for(proposal).run(state))
    spec = state.specification
    assert spec is not None
    assert spec.components == [] and spec.approach_id is None   # never silently re-anchored
    assert any("structural defects" in g for g in spec.gaps)


def test_idempotent_across_refine_rounds():
    state = _state()
    agent = _architect_for(_proposal())
    run(agent.run(state))
    first = state.specification
    run(agent.run(state))
    second = state.specification
    assert {q.id for q in first.quantities} == {q.id for q in second.quantities}
    assert len(second.quantities) == 3                          # no accumulation
