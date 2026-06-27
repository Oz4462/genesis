"""dimensional_guard wired into GATE δ-physics — the automatic dimensional-error check is now
reachable from the live gate, not just an island test.

The guard runs ONLY on the proven input-homogeneous validators (SCALE_INVARIANT_VALIDATORS), using
the per-input units the recipe already declares. A correct validator can never be false-flagged
(allowlist = proven homogeneous); a dimensionally inconsistent one fails the gate with
PHYSICS_DIMENSIONAL_INCONSISTENCY even if its physics margin is cleared.
"""

from __future__ import annotations

from gen.core.state import Quantity, Specification, ValueOrigin
from gen.physics_selection import select_physics_checks
from gen.physics_validation import (
    PhysicsCheck,
    VALIDATORS,
    gate_delta_physics,
    run_physics_checks,
)

# Proven-homogeneous electric_actuator inputs + the units the recipe carries (see
# tests/test_dimensional_invariance.py). A real validator, real units — the live path.
_EA_INPUTS = {
    "joint_torque": 28.0, "joint_speed": 3.0,
    "motor_stall_torque": 2.0, "motor_noload_speed": 300.0,
    "gear_ratio": 40.0, "efficiency": 0.85,
}
_EA_UNITS = {
    "joint_torque": "N*m", "joint_speed": "rad/s",
    "motor_stall_torque": "N*m", "motor_noload_speed": "rad/s",
    "gear_ratio": "1", "efficiency": "1",
}


def test_homogeneous_validator_passes_dimensional_check():
    # Arrange — a real, proven-homogeneous validator with its declared units
    check = PhysicsCheck("joint actuator", "electric_actuator", _EA_INPUTS, input_units=_EA_UNITS)

    # Act
    results = run_physics_checks([check])

    # Assert — the guard ran and confirmed scale-invariance; the gate is clean
    assert results[0]["dimensional_ok"] is True
    assert gate_delta_physics([check]).passed is True


def test_dimensionally_broken_validator_fails_the_gate(monkeypatch):
    # Arrange — replace a proven validator with one whose safety_factor ADDS a torque to an
    # angular speed (incommensurable): it clears its margin (ok=True) but is NOT scale-invariant.
    def broken(**kw):
        return {"ok": True, "safety_factor": kw["joint_torque"] + kw["joint_speed"]}

    monkeypatch.setitem(VALIDATORS, "electric_actuator", broken)
    check = PhysicsCheck("broken actuator", "electric_actuator", _EA_INPUTS, input_units=_EA_UNITS)

    # Act
    res = run_physics_checks([check])
    gate = gate_delta_physics([check])

    # Assert — non-vacuous: the dimensional bug is caught even though ok=True
    assert res[0]["ok"] is True and res[0]["dimensional_ok"] is False
    assert not gate.passed
    assert any(f.code == "PHYSICS_DIMENSIONAL_INCONSISTENCY" for f in gate.failures)


def test_missing_units_skips_dimensional_check_backward_compatible():
    # Arrange — an old-style check with no input_units (the pre-wire construction)
    check = PhysicsCheck("joint actuator", "electric_actuator", _EA_INPUTS)

    # Act
    res = run_physics_checks([check])

    # Assert — the guard is skipped (None), behaviour unchanged, gate still passes
    assert res[0]["dimensional_ok"] is None
    assert gate_delta_physics([check]).passed is True


def test_non_allowlisted_validator_is_not_dimensionally_checked():
    # Arrange — torsion is NOT in the proven set (it may carry a baked constant); even with
    # units present, the guard must not run on it (no false alarms on unproven validators).
    torsion_inputs = {
        "torque": 1.0e5, "diameter": 20.0, "length": 200.0,
        "shear_modulus_g": 79000.0, "shear_strength": 200.0,
    }
    torsion_units = {
        "torque": "N*mm", "diameter": "mm", "length": "mm",
        "shear_modulus_g": "MPa", "shear_strength": "MPa",
    }
    check = PhysicsCheck("shaft", "torsion", torsion_inputs, input_units=torsion_units)

    # Act
    res = run_physics_checks([check])

    # Assert — explicitly not checked (None), regardless of its physics verdict
    assert res[0]["dimensional_ok"] is None


def _q(qid, value, unit, measurand) -> Quantity:
    # a GROUNDED value must carry provenance (the no-source-no-value invariant)
    return Quantity(
        id=qid, name=qid, value=value, unit=unit, origin=ValueOrigin.GROUNDED,
        grounding=[f"claim-{qid}"], measurand=measurand,
    )


def test_select_physics_checks_populates_units_so_the_gate_runs_the_guard():
    # Arrange — a spec whose measurands trigger the electric_actuator recipe
    spec = Specification(
        run_id="r", idea="joint",
        quantities=[
            _q("t", 28.0, "N*m", "actuator.joint_torque"),
            _q("s", 3.0, "rad/s", "actuator.joint_speed"),
            _q("mt", 2.0, "N*m", "motor.stall_torque"),
            _q("ms", 300.0, "rad/s", "motor.noload_speed"),
            _q("g", 40.0, "1", "drivetrain.gear_ratio"),
            _q("e", 0.85, "1", "drivetrain.efficiency"),
        ],
    )

    # Act
    checks, gaps = select_physics_checks(spec)
    actuator = next(c for c in checks if c.validator == "electric_actuator")

    # Assert — units flowed from the recipe; the gate can (and does) run the dimensional guard
    assert actuator.input_units.get("joint_torque") == "N*m"
    assert run_physics_checks([actuator])[0]["dimensional_ok"] is True
