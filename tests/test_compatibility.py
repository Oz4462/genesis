"""Acceptance tests for component compatibility (Phase γ-depth §3), via gates.

"What fits perfectly together" is deterministic where it reduces to a numeric
match between grounded spec quantities: a shaft diameter EQUALS a bore diameter,
a device voltage EQUALS the supply voltage. Those are `eq` expression constraints
over GROUNDED quantities (each value verbatim from a claim, C-4). A mismatch is
caught (CONSTRAINT_VIOLATION); a compatibility the human did not declare is never
invented. Non-numeric compatibility (connector type) is a claim-backed statement,
not a deterministic check — honest about the boundary.

Run:  pytest tests/test_compatibility.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Constraint,
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


def _grounded(qid: str, value: float, unit: str, grounding: list[str]) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.GROUNDED, grounding=grounding)


def _state(quantities, constraints, claims) -> RunState:
    st = RunState(question=Question(raw="i", run_id="r"))
    st.claims = claims
    st.specification = Specification(
        run_id="r", idea="i", quantities=quantities, constraints=constraints,
    )
    return st


def _codes(state) -> set[str]:
    return {f.code for f in gate_gamma(state).failures}


# --- mechanical: a shaft fits a bearing bore (diameters equal) ----------------

def test_shaft_bore_dimension_match():
    shaft = _claim("c_shaft", "The motor shaft diameter is 5 mm.")
    bore = _claim("c_bore", "The 605ZZ bearing has a 5 mm bore.")
    qs = [_grounded("q_shaft", 5.0, "mm", ["c_shaft"]), _grounded("q_bore", 5.0, "mm", ["c_bore"])]
    con = [Constraint(id="k", kind="eq", left="q_shaft", right="q_bore",
                      reason="shaft must match the bearing bore")]
    assert gate_gamma(_state(qs, con, [shaft, bore])).passed


def test_dimension_mismatch_is_caught():
    shaft = _claim("c_shaft", "The motor shaft diameter is 6 mm.")
    bore = _claim("c_bore", "The 605ZZ bearing has a 5 mm bore.")
    qs = [_grounded("q_shaft", 6.0, "mm", ["c_shaft"]), _grounded("q_bore", 5.0, "mm", ["c_bore"])]
    con = [Constraint(id="k", kind="eq", left="q_shaft", right="q_bore", reason="must match")]
    assert "CONSTRAINT_VIOLATION" in _codes(_state(qs, con, [shaft, bore]))


# --- electrical: device voltage must match the supply -------------------------

def test_voltage_compatibility():
    dev = _claim("c_dev", "The Raspberry Pi 4 requires 5 V.")
    psu = _claim("c_psu", "The power supply provides 5 V.")
    qs = [_grounded("q_dev", 5.0, "V", ["c_dev"]), _grounded("q_psu", 5.0, "V", ["c_psu"])]
    con = [Constraint(id="k", kind="eq", left="q_dev", right="q_psu",
                      reason="supply voltage must match the device")]
    assert gate_gamma(_state(qs, con, [dev, psu])).passed


def test_voltage_mismatch_is_caught():
    dev = _claim("c_dev", "The Raspberry Pi 4 requires 5 V.")
    psu = _claim("c_psu", "The power supply provides 12 V.")
    qs = [_grounded("q_dev", 5.0, "V", ["c_dev"]), _grounded("q_psu", 12.0, "V", ["c_psu"])]
    con = [Constraint(id="k", kind="eq", left="q_dev", right="q_psu", reason="must match")]
    assert "CONSTRAINT_VIOLATION" in _codes(_state(qs, con, [dev, psu]))


# --- supply must meet the device current draw (>=) ----------------------------

def test_supply_current_must_meet_draw():
    draw = _claim("c_draw", "The Raspberry Pi 4 draws up to 3 A.")
    psu = _claim("c_psu", "The power supply delivers 5 A.")
    qs = [_grounded("q_draw", 3.0, "A", ["c_draw"]), _grounded("q_psu_a", 5.0, "A", ["c_psu"])]
    con = [Constraint(id="k", kind="ge", left="q_psu_a", right="q_draw",
                      reason="supply current must meet the device draw")]
    assert gate_gamma(_state(qs, con, [draw, psu])).passed


# --- anti-invention: no undeclared compatibility is assumed -------------------

def test_no_invented_compatibility():
    # two parts with different diameters, but NO compatibility constraint declared.
    # GENESIS must not assume they fit.
    shaft = _claim("c_shaft", "The motor shaft diameter is 6 mm.")
    bore = _claim("c_bore", "The bearing has a 5 mm bore.")
    qs = [_grounded("q_shaft", 6.0, "mm", ["c_shaft"]), _grounded("q_bore", 5.0, "mm", ["c_bore"])]
    assert gate_gamma(_state(qs, [], [shaft, bore])).passed   # nothing declared -> nothing checked
