"""GATE δ-physics — the validator-registry gate that aggregates engineering checks.

The gate passes only if every declared check actually ran and reported ok; an unknown
validator, a validator that raises, and a validator that clears no margin each produce a
distinct hard failure (never a silent pass). Offline, no LLM, pure functions.

Run:  pytest tests/test_physics_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.physics_validation import (  # noqa: E402
    VALIDATORS,
    PhysicsCheck,
    gate_delta_physics,
    run_physics_checks,
)

# a few checks with inputs that pass their own margin
_TORSION_OK = PhysicsCheck("drive shaft", "torsion", dict(
    torque=100000.0, diameter=20.0, length=1000.0, shear_modulus_g=80000.0, shear_strength=100.0))
_FATIGUE_OK = PhysicsCheck("bracket fillet", "fatigue", dict(
    stress_amplitude=80.0, mean_stress=60.0, uts=500.0, endurance=250.0))
_RESONANCE_OK = PhysicsCheck("mount", "resonance", dict(
    first_natural_hz=300.0, excitation_hz=100.0))


def test_all_passing_checks_pass_the_gate():
    result = gate_delta_physics([_TORSION_OK, _FATIGUE_OK, _RESONANCE_OK])
    assert result.gate == "delta-physics"
    assert result.passed and result.failures == []


def test_empty_checklist_passes_vacuously():
    result = gate_delta_physics([])
    assert result.passed and result.failures == []


def test_a_failing_check_fails_the_gate():
    # same shaft, but a weak material: max_shear ~63.7 MPa > 30 MPa strength -> not ok
    weak = PhysicsCheck("drive shaft", "torsion", dict(
        torque=100000.0, diameter=20.0, length=1000.0, shear_modulus_g=80000.0, shear_strength=30.0))
    result = gate_delta_physics([_TORSION_OK, weak])
    assert not result.passed
    codes = [f.code for f in result.failures]
    assert codes == ["PHYSICS_CHECK_FAILED"]
    assert "drive shaft" in result.failures[0].detail


def test_unknown_validator_is_a_hard_failure():
    result = gate_delta_physics([PhysicsCheck("mystery", "no_such_validator", {})])
    assert not result.passed
    assert result.failures[0].code == "PHYSICS_UNKNOWN_VALIDATOR"


def test_erroring_validator_is_surfaced_not_swallowed():
    # a zero diameter makes the torsion validator raise; the gate must FAIL, not pass
    bad = PhysicsCheck("broken shaft", "torsion", dict(
        torque=100000.0, diameter=0.0, length=1000.0, shear_modulus_g=80000.0, shear_strength=100.0))
    result = gate_delta_physics([bad])
    assert not result.passed
    assert result.failures[0].code == "PHYSICS_CHECK_ERROR"
    assert "broken shaft" in result.failures[0].detail


def test_run_physics_checks_returns_evidence():
    rows = run_physics_checks([_TORSION_OK, PhysicsCheck("x", "nope", {})])
    assert rows[0]["status"] == "ran" and rows[0]["ok"] is True
    assert rows[0]["result"]["safety_factor"] > 1.0          # the computed margin
    assert rows[1]["status"] == "unknown" and rows[1]["ok"] is False


def test_registry_exposes_the_expected_validators():
    for key in ("torsion", "buckling", "fatigue", "contact", "pressure_vessel",
                "creep", "overtemperature", "thermal_mismatch", "resonance",
                "notch_fatigue", "fracture", "plate_bending", "bolted_joint"):
        assert key in VALIDATORS and callable(VALIDATORS[key])


def test_mixed_batch_reports_each_distinct_failure():
    result = gate_delta_physics([
        _TORSION_OK,                                                    # ok
        PhysicsCheck("u", "ghost", {}),                                 # unknown
        PhysicsCheck("e", "torsion", dict(                              # error (d=0)
            torque=1.0, diameter=0.0, length=1.0, shear_modulus_g=1.0, shear_strength=1.0)),
        PhysicsCheck("f", "fatigue", dict(                             # failed margin
            stress_amplitude=300.0, mean_stress=300.0, uts=500.0, endurance=250.0)),
    ])
    assert not result.passed
    assert {f.code for f in result.failures} == {
        "PHYSICS_UNKNOWN_VALIDATOR", "PHYSICS_CHECK_ERROR", "PHYSICS_CHECK_FAILED"}
