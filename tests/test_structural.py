"""δ-layer-2: deterministic bending-stress statics, with NO new gate code.

The structural check rides entirely on the existing γ machinery: a weight
``F = m·g`` and a cantilever stress ``σ = 6·F·L/(b·h²)`` are DERIVED quantities
(GENESIS's safe evaluator computes them, GATE γ C-6 recomputes them), the result
is dimensionally verified as a pressure (C-15, the Mars-Orbiter guard), and the
material strength is a GROUNDED quantity whose number is verbatim from a claim
(C-1..C-4). A numeric constraint ``σ ≤ strength`` (C-13) is the verdict.

These tests pin all four properties, each in isolation:
  * the chain PASSES the gate and σ carries a pressure dimension;
  * an overload trips CONSTRAINT_VIOLATION (and nothing else);
  * an invented strength number trips VALUE_NOT_IN_GROUNDING (no fabricated value);
  * the formula helpers produce exactly the audited strings (no drift).

Offline, no LLM, no network.

Run:  pytest tests/test_structural.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Constraint,
    Derivation,
    Question,
    Quantity,
    RunState,
    SourceRef,
    SourceSupport,
    Specification,
    ValueOrigin,
)
from gen.structural import (  # noqa: E402
    STANDARD_GRAVITY,
    cantilever_bending_stress_formula,
    weight_formula,
)
from gen.verification.derivation import evaluate_formula  # noqa: E402
from gen.verification.gates import gate_gamma  # noqa: E402
from gen.verification.units import formula_dimension, parse_unit  # noqa: E402


def _claim(cid: str, text: str) -> Claim:
    return Claim(
        id=cid, text=text,
        sources=[SourceRef(f"https://{cid}", True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.95,
        verification=[SourceRef(f"https://i/{cid}", True, support=SourceSupport.SUPPORTS)],
    )


def _structural_state(
    *,
    strength_value: float,
    strength_text: str,
    load_value: float = 12.0,
    load_text: str = "A typical wall shelf must carry a load of 12 kg.",
) -> RunState:
    """A minimal spec carrying ONLY the statics chain (no components/steps, so no
    β-anchor is required). ``arm=60``, ``b=80``, ``h=6`` mm — the capstone section.

    σ and F are computed with the real evaluator, so the stored numbers can never
    silently drift from the formulas the helpers emit.
    """
    g_id, load_id, force_id = "q_g", "q_load", "q_force"
    arm_id, b_id, h_id, sigma_id, strength_id = "q_arm", "q_b", "q_h", "q_sigma", "q_strength"

    force_formula = weight_formula(load_id, g_id)
    sigma_formula = cantilever_bending_stress_formula(force_id, arm_id, b_id, h_id)

    base = {load_id: load_value, g_id: STANDARD_GRAVITY, arm_id: 60.0, b_id: 80.0, h_id: 6.0}
    force_val = evaluate_formula(force_formula, {load_id: load_value, g_id: STANDARD_GRAVITY})
    sigma_val = evaluate_formula(sigma_formula, {**base, force_id: force_val})

    quantities = [
        Quantity(id=load_id, name="load", value=load_value, unit="kg",
                 origin=ValueOrigin.GROUNDED, grounding=["c_load"]),
        Quantity(id=g_id, name="standard gravity", value=STANDARD_GRAVITY, unit="m/s^2",
                 origin=ValueOrigin.GROUNDED, grounding=["c_g"]),
        Quantity(id=force_id, name="weight", value=force_val, unit="N",
                 origin=ValueOrigin.DERIVED,
                 derivation=Derivation(formula=force_formula, inputs=(load_id, g_id))),
        Quantity(id=arm_id, name="lever arm", value=60.0, unit="mm",
                 origin=ValueOrigin.DECISION, rationale="shelf projection depth"),
        Quantity(id=b_id, name="section breadth", value=80.0, unit="mm",
                 origin=ValueOrigin.DECISION, rationale="plate breadth"),
        Quantity(id=h_id, name="section depth", value=6.0, unit="mm",
                 origin=ValueOrigin.DECISION, rationale="plate thickness in load direction"),
        Quantity(id=sigma_id, name="peak bending stress", value=sigma_val, unit="MPa",
                 origin=ValueOrigin.DERIVED,
                 derivation=Derivation(formula=sigma_formula,
                                       inputs=(force_id, arm_id, b_id, h_id))),
        Quantity(id=strength_id, name="material strength", value=strength_value, unit="MPa",
                 origin=ValueOrigin.GROUNDED, grounding=["c_strength"]),
    ]
    constraints = [
        Constraint(id="k_stress", kind="le", left=sigma_id, right=strength_id,
                   reason="bending stress must stay below the material strength"),
    ]
    spec = Specification(run_id="r", idea="cantilever statics",
                         quantities=quantities, constraints=constraints)
    st = RunState(question=Question(raw="statics", run_id="r"))
    st.claims = [
        _claim("c_load", load_text),
        _claim("c_g", "Standard gravity is defined as 9.80665 m/s^2."),
        _claim("c_strength", strength_text),
    ]
    st.specification = spec
    return st


# --- 1. the chain passes, and σ is dimensionally a pressure -------------------

def test_bending_chain_passes_gate():
    st = _structural_state(
        strength_value=50.0,
        strength_text="3D-printed PLA has a tensile strength of about 50 MPa.",
    )
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]

    # σ ≈ 6·117.68·60 / (80·36) ≈ 14.7 MPa, comfortably under 50 MPa
    sigma = next(q for q in st.specification.quantities if q.id == "q_sigma").value
    assert 14.0 < sigma < 15.0


def test_sigma_has_pressure_dimension():
    # independent of any spec: the formula's dimension IS a pressure (Pa == MPa dim)
    dims = {"q_force": parse_unit("N"), "q_arm": parse_unit("mm"),
            "q_b": parse_unit("mm"), "q_h": parse_unit("mm")}
    sigma_formula = cantilever_bending_stress_formula("q_force", "q_arm", "q_b", "q_h")
    assert formula_dimension(sigma_formula, dims) == parse_unit("Pa") == parse_unit("MPa")

    # and the weight formula is a force (newton)
    force_dims = {"q_load": parse_unit("kg"), "q_g": parse_unit("m/s^2")}
    assert formula_dimension(weight_formula("q_load", "q_g"), force_dims) == parse_unit("N")


# --- 2. an overload trips the constraint, and ONLY that -----------------------

def test_overload_trips_constraint_violation():
    # a weak material whose stated strength (10 MPa) IS verbatim in its claim, so
    # no C-4 noise — σ ≈ 14.7 MPa > 10 MPa is purely a CONSTRAINT_VIOLATION.
    st = _structural_state(
        strength_value=10.0,
        strength_text="This weak filament has a tensile strength of about 10 MPa.",
    )
    result = gate_gamma(st)
    codes = {f.code for f in result.failures}
    assert codes == {"CONSTRAINT_VIOLATION"}, [f"{f.code}: {f.detail}" for f in result.failures]


# --- 3. an invented strength number is caught (no fabricated value) -----------

def test_invented_strength_value_is_caught():
    # the claim says "about 50 MPa" but the quantity asserts 999 — a value that
    # does not appear in its grounding claim must never pass as GROUNDED (C-4).
    st = _structural_state(
        strength_value=999.0,
        strength_text="3D-printed PLA has a tensile strength of about 50 MPa.",
    )
    result = gate_gamma(st)
    codes = {f.code for f in result.failures}
    assert "VALUE_NOT_IN_GROUNDING" in codes, [f"{f.code}: {f.detail}" for f in result.failures]


# --- 4. the formula helpers do not drift from the audited strings -------------

def test_formula_helpers_are_exact():
    assert weight_formula("q_load", "q_g") == "q_load * q_g"
    assert (
        cantilever_bending_stress_formula("q_force", "q_arm", "q_b", "q_h")
        == "6 * q_force * q_arm / (q_b * q_h * q_h)"
    )
    assert STANDARD_GRAVITY == 9.80665
