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
    BOLT_SHEAR_COEFFICIENT_88,
    BOLT_UTS_CLASS_88_MPA,
    M4_TENSILE_STRESS_AREA_MM2,
    STANDARD_GRAVITY,
    STRESS_CONCENTRATION_CIRCULAR_HOLE,
    bolt_shear_capacity_formula,
    cantilever_bending_stress_formula,
    peak_stress_formula,
    per_fastener_shear_formula,
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
    assert peak_stress_formula("q_snom", "q_kt") == "q_kt * q_snom"
    assert (
        bolt_shear_capacity_formula("q_c", "q_uts", "q_a") == "q_c * q_uts * q_a"
    )
    assert per_fastener_shear_formula("q_force", "q_n") == "q_force / q_n"
    assert STANDARD_GRAVITY == 9.80665
    assert STRESS_CONCENTRATION_CIRCULAR_HOLE == 3.0
    assert BOLT_SHEAR_COEFFICIENT_88 == 0.6
    assert BOLT_UTS_CLASS_88_MPA == 800.0
    assert M4_TENSILE_STRESS_AREA_MM2 == 8.78


# --- residual-risk closure: safety factor + Kirsch hole stress concentration ----
#
# The bare bending check (σ_nom ≤ strength) was necessary, not sufficient. The
# fuller check applies the declared safety factor to the load AND the Kirsch
# Kt=3 hole stress raiser, then re-tests against the in-plane strength. All
# DERIVED values are recomputed with the real evaluator, so a stored number can
# never silently drift from its formula.

def _grounded(qid, value, unit, claim_id):
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.GROUNDED, grounding=[claim_id])


def _decision(qid, value, unit):
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="declared")


def _derived(qid, value, unit, formula, inputs):
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DERIVED,
                    derivation=Derivation(formula=formula, inputs=inputs))


def _peak_stress_state(
    *,
    thickness: float,
    strength_value: float,
    strength_text: str,
    load_kg: float = 12.0,
    sf: float = 2.0,
    arm: float = 60.0,
    breadth: float = 80.0,
) -> RunState:
    kt = STRESS_CONCENTRATION_CIRCULAR_HOLE
    f_design = weight_formula("q_design", "q_g")
    f_snom = cantilever_bending_stress_formula("q_force", "q_arm", "q_b", "q_h")
    f_speak = peak_stress_formula("q_snom", "q_kt")

    design_val = evaluate_formula("q_load * q_sf", {"q_load": load_kg, "q_sf": sf})
    force_val = evaluate_formula(f_design, {"q_design": design_val, "q_g": STANDARD_GRAVITY})
    snom_val = evaluate_formula(
        f_snom, {"q_force": force_val, "q_arm": arm, "q_b": breadth, "q_h": thickness})
    speak_val = evaluate_formula(f_speak, {"q_snom": snom_val, "q_kt": kt})

    quantities = [
        _grounded("q_load", load_kg, "kg", "c_load"),
        _decision("q_sf", sf, "1"),
        _derived("q_design", design_val, "kg", "q_load * q_sf", ("q_load", "q_sf")),
        _grounded("q_g", STANDARD_GRAVITY, "m/s^2", "c_g"),
        _derived("q_force", force_val, "N", f_design, ("q_design", "q_g")),
        _decision("q_arm", arm, "mm"),
        _decision("q_b", breadth, "mm"),
        _decision("q_h", thickness, "mm"),
        _derived("q_snom", snom_val, "MPa", f_snom, ("q_force", "q_arm", "q_b", "q_h")),
        _grounded("q_kt", kt, "1", "c_kirsch"),
        _derived("q_speak", speak_val, "MPa", f_speak, ("q_snom", "q_kt")),
        _grounded("q_strength", strength_value, "MPa", "c_strength"),
    ]
    spec = Specification(
        run_id="r", idea="peak stress", quantities=quantities,
        constraints=[Constraint(id="k_stress", kind="le", left="q_speak",
                                right="q_strength", reason="peak stress below strength")],
    )
    st = RunState(question=Question(raw="peak", run_id="r"))
    st.claims = [
        _claim("c_load", "A typical wall shelf must carry a load of 12 kg."),
        _claim("c_g", "Standard gravity is defined as 9.80665 m/s^2."),
        _claim("c_kirsch", "A circular hole in a plate under tension has a stress "
                           "concentration factor of 3 (Kirsch solution)."),
        _claim("c_strength", strength_text),
    ]
    st.specification = spec
    return st


def test_peak_stress_chain_passes_for_the_thick_section():
    # the 12 mm redesign: σ_peak ≈ 22 MPa under the 24 kg design load, < 50 MPa
    st = _peak_stress_state(
        thickness=12.0, strength_value=50.0,
        strength_text="FDM-printed PLA loaded in-plane has a tensile strength of about 50 MPa.")
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]
    speak = next(q for q in st.specification.quantities if q.id == "q_speak").value
    assert 21.0 < speak < 23.0


def test_thin_section_overstresses_the_hole():
    # the residual-risk check has TEETH: the original 6 mm plate, once the safety
    # factor and the Kt=3 hole raiser are counted, gives σ_peak ≈ 88 MPa > 50 MPa.
    # The strength value (50) is verbatim in its claim, so this is purely a
    # CONSTRAINT_VIOLATION — exactly what forced the redesign to 12 mm.
    st = _peak_stress_state(
        thickness=6.0, strength_value=50.0,
        strength_text="FDM-printed PLA loaded in-plane has a tensile strength of about 50 MPa.")
    result = gate_gamma(st)
    codes = {f.code for f in result.failures}
    assert codes == {"CONSTRAINT_VIOLATION"}, [f"{f.code}: {f.detail}" for f in result.failures]


def test_peak_stress_keeps_pressure_dimension():
    # σ_peak = Kt · σ_nom : a dimensionless factor times a pressure stays a pressure
    dims = {"q_snom": parse_unit("MPa"), "q_kt": parse_unit("1")}
    assert formula_dimension(peak_stress_formula("q_snom", "q_kt"), dims) == parse_unit("MPa")


# --- residual-risk closure: fastener shear (EN 1993-1-8, bracket-side) ----------

def _fastener_state(*, force_value: float, n_screws: float = 2.0) -> RunState:
    f_cap = bolt_shear_capacity_formula("q_coeff", "q_uts", "q_area")
    f_dem = per_fastener_shear_formula("q_force", "q_n")
    cap_val = evaluate_formula(f_cap, {"q_coeff": BOLT_SHEAR_COEFFICIENT_88,
                                       "q_uts": BOLT_UTS_CLASS_88_MPA,
                                       "q_area": M4_TENSILE_STRESS_AREA_MM2})
    dem_val = evaluate_formula(f_dem, {"q_force": force_value, "q_n": n_screws})
    quantities = [
        _grounded("q_coeff", BOLT_SHEAR_COEFFICIENT_88, "1", "c_coeff"),
        _grounded("q_uts", BOLT_UTS_CLASS_88_MPA, "MPa", "c_uts"),
        _grounded("q_area", M4_TENSILE_STRESS_AREA_MM2, "mm^2", "c_area"),
        _derived("q_cap", cap_val, "N", f_cap, ("q_coeff", "q_uts", "q_area")),
        _decision("q_force", force_value, "N"),
        _decision("q_n", n_screws, "1"),
        _derived("q_dem", dem_val, "N", f_dem, ("q_force", "q_n")),
    ]
    spec = Specification(
        run_id="r", idea="fastener", quantities=quantities,
        constraints=[Constraint(id="k_shear", kind="le", left="q_dem", right="q_cap",
                                reason="shear demand below capacity")],
    )
    st = RunState(question=Question(raw="shear", run_id="r"))
    st.claims = [
        _claim("c_coeff", "EN 1993-1-8 gives a shear coefficient of 0.6 for property "
                          "class 8.8 bolts."),
        _claim("c_uts", "An ISO 898-1 property class 8.8 screw has an ultimate tensile "
                        "strength of 800 MPa."),
        _claim("c_area", "An M4 coarse-pitch screw has a tensile stress area of 8.78 mm^2."),
    ]
    st.specification = spec
    return st


def test_fastener_shear_capacity_dimension_is_a_force():
    # αv · f_ub · A_s : dimensionless · pressure · area = force (MPa·mm² = N)
    dims = {"q_coeff": parse_unit("1"), "q_uts": parse_unit("MPa"), "q_area": parse_unit("mm^2")}
    assert formula_dimension(
        bolt_shear_capacity_formula("q_coeff", "q_uts", "q_area"), dims) == parse_unit("N")


def test_fastener_shear_passes_at_the_design_load():
    # design-load force 235.36 N over 2 screws = 117.68 N per screw vs ~4214 N capacity
    st = _fastener_state(force_value=24.0 * STANDARD_GRAVITY)
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]
    cap = next(q for q in st.specification.quantities if q.id == "q_cap").value
    assert 4200.0 < cap < 4230.0


def test_fastener_shear_overload_trips_constraint():
    # an absurd 20 kN load shears the screws: demand 10 kN/screw > 4.2 kN capacity
    st = _fastener_state(force_value=20000.0)
    codes = {f.code for f in gate_gamma(st).failures}
    assert codes == {"CONSTRAINT_VIOLATION"}, codes
