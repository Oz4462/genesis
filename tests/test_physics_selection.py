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
    assert len(gaps) == 1 and "not dimensionally" in gaps[0]


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
