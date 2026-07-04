"""Auto-selection of physics checks from a Specification — the spec→gate wiring.

A measurand-tagged quantity set must yield exactly the applicable, unit-correct checks;
a declared physics whose input is missing or dimensionally wrong must become an explicit
GAP, never a silent drop or a wrong-unit number; an absent trigger must contribute
nothing. Offline, no LLM, pure functions.

Run:  pytest tests/test_physics_selection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.state import Quantity, Specification, ValueOrigin  # noqa: E402
from gen.physics_selection import (  # noqa: E402
    evaluate_spec_physics,
    select_physics_checks,
)


def _q(qid: str, value: float, unit: str, measurand: str) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="x", measurand=measurand)


def _shaft_quantities(shear_strength: float = 100.0) -> list[Quantity]:
    return [
        _q("t", 5.0, "N*m", "shaft.torque"),                       # 5 N*m -> 5000 N*mm
        _q("d", 20.0, "mm", "shaft.diameter"),
        _q("L", 1000.0, "mm", "shaft.length"),
        _q("G", 80000.0, "MPa", "material.shear_modulus"),
        _q("tau", shear_strength, "MPa", "material.shear_strength"),
    ]


def _fatigue_quantities() -> list[Quantity]:
    return [
        _q("sa", 80.0, "MPa", "fatigue.stress_amplitude"),
        _q("sm", 60.0, "MPa", "fatigue.mean_stress"),
        _q("uts", 500.0, "MPa", "material.uts"),
        _q("se", 250.0, "MPa", "material.endurance_limit"),
    ]


def _spec(quantities: list[Quantity]) -> Specification:
    return Specification(run_id="r", idea="x", quantities=quantities)


def test_selects_applicable_checks_and_passes_the_gate():
    spec = _spec(_shaft_quantities() + _fatigue_quantities())
    checks, gaps = select_physics_checks(spec)
    assert {c.validator for c in checks} == {"torsion", "fatigue"}
    assert gaps == []
    result = evaluate_spec_physics(spec)
    assert result["gate"].passed and len(result["checks"]) == 2 and result["gaps"] == []


def test_units_are_converted_soundly():
    # torque declared in N*m must reach the torsion validator as N*mm (x1000)
    checks, _ = select_physics_checks(_spec(_shaft_quantities()))
    torsion = next(c for c in checks if c.validator == "torsion")
    assert torsion.inputs["torque"] == 5000.0


def test_missing_input_becomes_a_gap_not_a_silent_drop():
    # the shaft torque is declared (trigger present) but the shear strength is not
    qs = [q for q in _shaft_quantities() if q.measurand != "material.shear_strength"]
    checks, gaps = select_physics_checks(_spec(qs))
    assert checks == []
    assert len(gaps) == 1 and "material.shear_strength" in gaps[0]


def test_dimension_mismatch_becomes_a_gap():
    qs = _shaft_quantities()
    qs[1] = _q("d", 20.0, "kg", "shaft.diameter")              # diameter in a mass unit
    checks, gaps = select_physics_checks(_spec(qs))
    assert checks == []
    assert len(gaps) == 1 and "nicht dimensionsgleich" in gaps[0]


def test_absent_trigger_contributes_nothing():
    spec = _spec([_q("w", 50.0, "mm", "geometry.width")])      # no physics trigger at all
    checks, gaps = select_physics_checks(spec)
    assert checks == [] and gaps == []


def test_a_failing_selected_check_fails_the_gate():
    # this shaft's surface shear is 16*5000/(pi*20^3) ~ 3.18 MPa; a 2 MPa strength fails
    result = evaluate_spec_physics(_spec(_shaft_quantities(shear_strength=2.0)))
    assert len(result["checks"]) == 1 and not result["gate"].passed
    assert result["gate"].failures[0].code == "PHYSICS_CHECK_FAILED"


def test_is_deterministic():
    spec = _spec(_shaft_quantities() + _fatigue_quantities())
    a, ga = select_physics_checks(spec)
    b, gb = select_physics_checks(spec)
    assert [c.inputs for c in a] == [c.inputs for c in b] and ga == gb


# --- printability recipes -------------------------------------------------------

def test_printability_quantities_select_their_checks():
    spec = _spec([
        _q("bs", 0.8, "cm", "feature.bridge_span"),            # 0.8 cm -> 8 mm
        _q("cl", 0.25, "mm", "fit.clearance"),
        _q("pin", 4.0, "mm", "feature.pin_diameter"),
        _q("thr", 6.0, "mm", "feature.thread_major_diameter"),
        _q("wall", 1.2, "mm", "feature.unsupported_wall_thickness"),
        _q("emb", 1.0, "mm", "feature.emboss_width"),
        _q("sz", 10.0, "MPa", "print.stress_across_layers"),
        _q("uts", 50.0, "MPa", "material.uts"),
    ])
    checks, gaps = select_physics_checks(spec)
    assert gaps == []
    assert {c.validator for c in checks} == {
        "bridge_span", "fdm_fit_clearance", "pin_diameter", "thread_size",
        "unsupported_wall", "emboss_detail", "layer_adhesion",
    }
    bridge = next(c for c in checks if c.validator == "bridge_span")
    assert bridge.inputs["span"] == 8.0                        # sound cm -> mm
    result = evaluate_spec_physics(spec)
    assert result["gate"].passed and len(result["checks"]) == 7


def test_cross_layer_load_without_uts_is_a_gap():
    checks, gaps = select_physics_checks(_spec([
        _q("sz", 10.0, "MPa", "print.stress_across_layers"),
    ]))
    assert checks == []
    assert len(gaps) == 1 and "material.uts" in gaps[0]


def test_drone_quantities_select_the_flight_checks():
    # a drone spec in declared units: the recipes convert soundly (g -> kg,
    # cm^2 -> m^2, mAh -> Ah) and the full flight axis runs through the gate.
    spec = _spec([
        _q("m", 1200.0, "g", "vehicle.mass"),               # 1.2 kg
        _q("A", 500.0, "cm^2", "rotor.disk_area"),          # 0.05 m^2
        _q("n", 4.0, "1", "rotor.count"),
        _q("T", 30.0, "N", "rotor.max_total_thrust"),
        _q("cap", 50.0, "Wh", "battery.capacity"),
        _q("ph", 100.0, "W", "flight.hover_power"),
        _q("te", 20.0, "min", "flight.required_endurance"),
        _q("pm", 500.0, "W", "flight.max_power"),
        _q("u", 14.8, "V", "battery.voltage"),
        _q("esc", 40.0, "A", "esc.current_limit"),
        _q("cah", 1300.0, "mAh", "battery.capacity_ah"),    # 1.3 Ah
        _q("c", 50.0, "1", "battery.c_rating"),
        _q("ix", 0.02, "kg*m^2", "vehicle.attitude_inertia"),
        _q("kp", 2.0, "N*m", "control.attitude_kp"),
        _q("kd", 0.28, "N*m*s", "control.attitude_kd"),
    ])
    checks, gaps = select_physics_checks(spec)
    assert gaps == []
    assert {c.validator for c in checks} == {
        "rotor_hover", "battery_endurance", "current_budget", "attitude_pd",
    }
    hover = next(c for c in checks if c.validator == "rotor_hover")
    assert hover.inputs["mass"] == pytest.approx(1.2)              # g -> kg
    assert hover.inputs["rotor_disk_area"] == pytest.approx(0.05)  # cm^2 -> m^2
    budget = next(c for c in checks if c.validator == "current_budget")
    assert budget.inputs["battery_capacity_ah"] == pytest.approx(1.3)  # mAh -> Ah
    result = evaluate_spec_physics(spec)
    assert result["gate"].passed and len(result["checks"]) == 4


def test_underpowered_drone_fails_the_gate():
    # 1.2 kg needs >= 23.5 N for the 2:1 rule; 15 N is a definite no-fly
    spec = _spec([
        _q("m", 1.2, "kg", "vehicle.mass"),
        _q("A", 0.05, "m^2", "rotor.disk_area"),
        _q("n", 4.0, "1", "rotor.count"),
        _q("T", 15.0, "N", "rotor.max_total_thrust"),
    ])
    result = evaluate_spec_physics(spec)
    assert not result["gate"].passed
    assert result["gate"].failures[0].code == "PHYSICS_CHECK_FAILED"


def test_a_delaminating_cross_layer_load_fails_the_gate():
    # 30 MPa across the layers passes the quoted 50 MPa -- and still fails against
    # the retained 45 % (22.5 MPa): the print delaminates, the gate must say so.
    result = evaluate_spec_physics(_spec([
        _q("sz", 30.0, "MPa", "print.stress_across_layers"),
        _q("uts", 50.0, "MPa", "material.uts"),
    ]))
    assert not result["gate"].passed
    assert result["gate"].failures[0].code == "PHYSICS_CHECK_FAILED"


# --- Schritt-7-Review-Fixes physics_selection (2026-07-04): S-F1/S-F2/S-F3/S-F6 ---

def _q_m(qid, value, unit, measurand):
    return _q(qid, value, unit, measurand)


def _spec_with(quantities):
    return Specification(run_id="sel-fix", idea="test", quantities=quantities)


def test_dose_units_sv_and_prefixed_msv_resolve():
    """S-F6: Sv/Gy are known dimensions; mSv converts to Sv (factor 1e-3);
    Sv and Gy do NOT silently interconvert (quality factor is not dimensionless)."""
    from gen.verification.units import parse_unit, unit_scale
    assert parse_unit("mSv") == parse_unit("Sv")
    assert unit_scale("mSv") == 1e-3 and unit_scale("Sv") == 1.0
    assert parse_unit("Sv") != parse_unit("Gy")
    assert parse_unit("Sv") != parse_unit("J/kg")


def test_optional_input_present_but_unresolvable_is_gap_not_zero():
    """S-F2: a DECLARED dose in a wrong-dimension unit must become a gap —
    never silently 0.0 (which would green-light the dose check)."""
    spec = _spec_with([
        _q_m("q_abs", 100.0, "W", "thermal.radiation_absorbed"),
        _q_m("q_eps", 0.8, "1", "material.emissivity"),
        _q_m("q_area", 1.0, "m^2", "surface.area"),
        _q_m("q_t", 300.0, "K", "thermal.temperature"),
        _q_m("q_dose", 20.0, "K", "radiation.total_ionizing_dose"),  # wrong dimension!
    ])
    checks, gaps = select_physics_checks(spec)
    fired = {c.validator for c in checks}
    assert "vacuum_radiation_balance" not in fired
    assert any("total_ionizing_dose" in g for g in gaps)


def test_optional_input_msv_converts_to_sv():
    """S-F2+S-F6 positive path: dose declared in mSv resolves and converts."""
    spec = _spec_with([
        _q_m("q_abs", 100.0, "W", "thermal.radiation_absorbed"),
        _q_m("q_eps", 0.8, "1", "material.emissivity"),
        _q_m("q_area", 1.0, "m^2", "surface.area"),
        _q_m("q_t", 300.0, "K", "thermal.temperature"),
        _q_m("q_dose", 250.0, "mSv", "radiation.total_ionizing_dose"),
    ])
    checks, gaps = select_physics_checks(spec)
    vac = next(c for c in checks if c.validator == "vacuum_radiation_balance")
    assert abs(vac.inputs["radiation_dose_sv"] - 0.25) < 1e-12
    assert not any("total_ionizing_dose" in g for g in gaps)


def test_absent_optional_input_still_defaults_without_gap():
    """S-F2 must not regress the documented absent->0.0 path."""
    spec = _spec_with([
        _q_m("q_abs", 100.0, "W", "thermal.radiation_absorbed"),
        _q_m("q_eps", 0.8, "1", "material.emissivity"),
        _q_m("q_area", 1.0, "m^2", "surface.area"),
        _q_m("q_t", 300.0, "K", "thermal.temperature"),
    ])
    checks, gaps = select_physics_checks(spec)
    vac = next(c for c in checks if c.validator == "vacuum_radiation_balance")
    assert vac.inputs["radiation_dose_sv"] == 0.0
    assert not gaps


def test_all_siblings_present_but_missing_trigger_becomes_gap():
    """S-F1: every non-trigger input of the torsion recipe present, only the
    trigger measurand absent (typo'd) -> an honest gap, not silent nothing."""
    spec = _spec_with([
        _q_m("q_d", 0.02, "m", "shaft.diameter"),
        _q_m("q_l", 0.5, "m", "shaft.length"),
        _q_m("q_g", 8.0e10, "Pa", "material.shear_modulus"),
        _q_m("q_tau", 2.0e8, "Pa", "material.shear_strength"),
        # trigger shaft.torque MISSING (e.g. tagged "shaft.torqe")
    ])
    checks, gaps = select_physics_checks(spec)
    assert not any(c.validator == "torsion" for c in checks)
    assert any("shaft.torque" in g and "torsion" in g for g in gaps)


def test_two_stray_material_measurands_do_not_gap():
    """S-F1 negative: partial sibling presence (< all) stays silent — generic
    material data alone must not spam gaps for unrelated physics."""
    spec = _spec_with([
        _q_m("q_g", 8.0e10, "Pa", "material.shear_modulus"),
        _q_m("q_tau", 2.0e8, "Pa", "material.shear_strength"),
    ])
    checks, gaps = select_physics_checks(spec)
    assert not gaps and not checks


def test_evaluate_spec_physics_reports_honest_pass():
    """S-F3: the combined honest verdict (gate passed AND no gaps) ships in the
    result so the safe value is the convenient one."""
    spec_gap = _spec_with([
        _q_m("q_d", 0.02, "m", "shaft.diameter"),
        _q_m("q_l", 0.5, "m", "shaft.length"),
        _q_m("q_g", 8.0e10, "Pa", "material.shear_modulus"),
        _q_m("q_tau", 2.0e8, "Pa", "material.shear_strength"),
    ])
    res = evaluate_spec_physics(spec_gap)
    assert res["gate"].passed is True          # nothing assembled -> vacuous gate
    assert res["gaps"]                          # but the sibling gap is there
    assert res["honest_pass"] is False          # and the honest verdict says so
