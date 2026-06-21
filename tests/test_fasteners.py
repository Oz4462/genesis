"""Acceptance tests for fastener → hole-size (Phase γ-depth §2), via existing gates.

A "norm screw → recommended drill diameter" mapping is REFERENCE DATA, so it must
be a sourced claim, never hardcoded: the hole-diameter quantity is GROUNDED in an
ISO-273-style claim and its value must appear verbatim (C-4). The hole TYPE
(clearance / threaded / heat-set insert) is a declared DECISION. The fit is an
expression constraint (hole >= screw + clearance). These tests prove the whole
pattern through GATE γ and the anti-invention guarantee — a drill value not in any
claim is rejected. No new engine; reference data comes from live α-research later.

Run:  pytest tests/test_fasteners.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Constraint,
    Decision,
    Question,
    Quantity,
    RunState,
    SourceRef,
    SourceSupport,
    Specification,
    ValueOrigin,
)
from gen.verification.gates import gate_gamma  # noqa: E402


def _claim(cid: str, text: str) -> Claim:
    return Claim(
        id=cid, text=text,
        sources=[SourceRef(f"https://{cid}", True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.9,
        verification=[SourceRef(f"https://i/{cid}", True, support=SourceSupport.SUPPORTS)],
    )


SCREW_CLAIM = _claim("c_m4", "An M4 screw has a nominal diameter of 4 mm.")
HOLE_CLAIM = _claim("c_iso273",
                    "ISO 273 specifies a medium clearance hole diameter of 4.5 mm for an M4 screw.")


def _grounded(qid: str, value: float, grounding: list[str]) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.GROUNDED, grounding=grounding)


def _state(quantities, constraints, decisions, claims) -> RunState:
    st = RunState(question=Question(raw="i", run_id="r"))
    st.claims = claims
    st.specification = Specification(
        run_id="r", idea="i", quantities=quantities, constraints=constraints, decisions=decisions,
    )
    return st


def _codes(state) -> set[str]:
    return {f.code for f in gate_gamma(state).failures}


# --- the pattern: claim-backed drill diameter + declared hole type + fit -------

def test_clearance_hole_pattern_passes():
    qs = [
        _grounded("q_screw_d", 4.0, ["c_m4"]),
        _grounded("q_hole_d", 4.5, ["c_iso273"]),     # value 4.5 is verbatim in the ISO claim
    ]
    decisions = [
        Decision(id="d_hole", title="Hole type", choice="through / clearance hole",
                 rationale="bolt passes through; ISO 273 medium series", informed_by=["c_iso273"]),
    ]
    constraints = [
        Constraint(id="k_fit", kind="ge", left="q_hole_d", right="q_screw_d",
                   reason="clearance hole must admit the screw"),
    ]
    state = _state(qs, constraints, decisions, [SCREW_CLAIM, HOLE_CLAIM])
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


# --- anti-invention: a drill value not in any claim is rejected ---------------

def test_invented_drill_diameter_is_rejected():
    qs = [
        _grounded("q_screw_d", 4.0, ["c_m4"]),
        _grounded("q_hole_d", 4.7, ["c_iso273"]),     # 4.7 is NOT in the ISO claim (says 4.5)
    ]
    state = _state(qs, [], [], [SCREW_CLAIM, HOLE_CLAIM])
    assert "VALUE_NOT_IN_GROUNDING" in _codes(state)


# --- threaded hole: tap-drill diameter grounded in its own reference claim -----

def test_threaded_hole_uses_grounded_tap_drill():
    tap = _claim("c_tap", "The tap drill for an M4x0.7 thread is 3.3 mm.")
    qs = [
        _grounded("q_tap", 3.3, ["c_tap"]),           # 3.3 verbatim in the tap claim
    ]
    decisions = [
        Decision(id="d_thread", title="Hole type", choice="threaded (M4x0.7)",
                 rationale="self-tapped thread in the printed part", informed_by=["c_tap"]),
    ]
    state = _state(qs, [], decisions, [tap])
    assert gate_gamma(state).passed


# --- heat-set insert: bore grounded; clearance to the screw still a constraint -

def test_heat_set_insert_bore_grounded_and_fit_checked():
    insert = _claim("c_insert", "The recommended bore for an M4 heat-set insert is 5.6 mm.")
    qs = [
        _grounded("q_screw_d", 4.0, ["c_m4"]),
        _grounded("q_bore", 5.6, ["c_insert"]),
    ]
    decisions = [
        Decision(id="d_insert", title="Hole type", choice="heat-set insert (M4)",
                 rationale="threaded brass insert for repeated assembly", informed_by=["c_insert"]),
    ]
    # the insert bore must exceed the screw (sanity), declared as a fit
    constraints = [
        Constraint(id="k", kind="gt", left="q_bore", right="q_screw_d", reason="bore admits insert"),
    ]
    state = _state(qs, constraints, decisions, [SCREW_CLAIM, insert])
    assert gate_gamma(state).passed
