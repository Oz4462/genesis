"""Physics / structural rework invariants (REWORK campaign 2026-07-11)."""

from __future__ import annotations


import pytest

from gen.physics_validation import (
    PhysicsCheck,
    VALIDATORS,
    _dimensional_ok,
    gate_delta_physics,
    run_physics_checks,
)
from gen.section_optimizer import StructuralProposal, propose_structural


_EA_INPUTS = {
    "joint_torque": 28.0,
    "joint_speed": 3.0,
    "motor_stall_torque": 2.0,
    "motor_noload_speed": 300.0,
    "gear_ratio": 40.0,
    "efficiency": 0.85,
}
_EA_UNITS = {
    "joint_torque": "N*m",
    "joint_speed": "rad/s",
    "motor_stall_torque": "N*m",
    "motor_noload_speed": "rad/s",
    "gear_ratio": "1",
    "efficiency": "1",
}


# --- dimensional guard: non-finite safety_factor is never "ok" --------------


def test_dimensional_ok_false_when_result_safety_factor_nonfinite():
    assert (
        _dimensional_ok(
            "electric_actuator",
            _EA_INPUTS,
            _EA_UNITS,
            {"ok": True, "safety_factor": float("nan")},
        )
        is False
    )


def test_run_physics_checks_flags_nonfinite_safety_factor(monkeypatch):
    def nan_ok(**kw):
        return {"ok": True, "safety_factor": float("nan")}

    monkeypatch.setitem(VALIDATORS, "electric_actuator", nan_ok)
    check = PhysicsCheck("ea", "electric_actuator", _EA_INPUTS, input_units=_EA_UNITS)
    res = run_physics_checks([check])[0]
    assert res["status"] == "error" or res["ok"] is False
    assert res["dimensional_ok"] is not True
    gate = gate_delta_physics([check])
    assert gate.passed is False


# --- section proposer: gate failure must not look like success ---------------


def test_propose_structural_section_unknown_type_raises():
    with pytest.raises(ValueError, match="design_type"):
        propose_structural(design_type="warp_drive")


def test_propose_structural_section_infeasible_is_nicht_optimiert():
    # Impossible: allow stress tiny vs force/arm so no feasible h in range.
    prop = propose_structural(
        design_type="section",
        force=1e6,
        arm=1e3,
        sigma_allow=1.0,
        min_wall=1.0,
        max_wall=2.0,
    )
    assert isinstance(prop, StructuralProposal)
    assert prop.design_type == "section"
    assert prop.verdict == "nicht_optimiert"
    assert prop.payload.feasible is False


def test_propose_structural_section_feasible_is_unverified_proposal():
    prop = propose_structural(
        design_type="section",
        force=100.0,
        arm=50.0,
        sigma_allow=200.0,
        min_wall=1.0,
        max_wall=40.0,
    )
    assert prop.verdict == "vorschlag_unverifiziert"
    assert prop.payload.feasible is True
    # Never claim certified from the proposer alone.
    assert "unverified" in prop.verdict or "vorschlag" in prop.verdict
