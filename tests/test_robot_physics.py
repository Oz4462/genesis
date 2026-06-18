"""End-to-end acceptance: a humanoid-leg Specification fires the new robot physics axes through
the SAME gate as every other GENESIS measurand — auto-selected from measurand tags, unit-converted,
and aggregated into one honest verdict. A well-sized leg passes; an under-sized knee actuator fails
honestly (not a masked pass); a missing input becomes an explicit gap, never a silent drop.

Offline, no LLM. Run:  pytest tests/test_robot_physics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.state import Quantity, Specification, ValueOrigin  # noqa: E402
from gen.physics_selection import evaluate_spec_physics, select_physics_checks  # noqa: E402


def _q(qid: str, value: float, unit: str, measurand: str) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="x", measurand=measurand)


def _leg_quantities(knee_torque: float = 30.0) -> list[Quantity]:
    """A humanoid leg/arm: 2R reach, ZMP balance, an electric knee actuator, and onboard compute."""
    return [
        _q("l1", 0.4, "m", "arm.link1_length"), _q("l2", 0.4, "m", "arm.link2_length"),
        _q("tx", 0.5, "m", "arm.target_x"), _q("ty", 0.1, "m", "arm.target_y"),
        _q("cx", 0.02, "m", "balance.com_x"), _q("ch", 0.9, "m", "balance.com_height"),
        _q("smin", -0.10, "m", "balance.support_min_x"), _q("smax", 0.12, "m", "balance.support_max_x"),
        _q("jt", knee_torque, "N*m", "actuator.joint_torque"), _q("js", 3.0, "rad/s", "actuator.joint_speed"),
        _q("mst", 2.0, "N*m", "motor.stall_torque"), _q("mns", 300.0, "rad/s", "motor.noload_speed"),
        _q("gr", 40.0, "1", "drivetrain.gear_ratio"), _q("eff", 0.85, "1", "drivetrain.efficiency"),
        _q("wt", 35.0, "1", "compute.workload_tops"), _q("ct", 100.0, "1", "compute.chip_tops"),
        _q("util", 0.6, "1", "compute.utilisation"), _q("etw", 5.0, "1", "compute.efficiency_tops_per_w"),
        _q("pb", 15.0, "W", "compute.power_budget"),
        _q("iops", 3e9, "1", "compute.inference_ops"), _q("tput", 4e12, "1", "compute.throughput_ops_per_s"),
        _q("cp", 0.01, "s", "control.period"),
    ]


def _spec(quantities: list[Quantity]) -> Specification:
    return Specification(run_id="r", idea="humanoid leg", quantities=quantities)


def test_leg_spec_auto_selects_the_robot_checks():
    """The measurand tags alone select the six applicable robot validators — no hand-wiring."""
    checks, gaps = select_physics_checks(_spec(_leg_quantities()))
    selected = {c.validator for c in checks}
    assert {"reach", "zmp_balance", "electric_actuator",
            "compute_budget", "inference_power", "inference_latency"} <= selected
    assert gaps == []


def test_units_are_converted_into_the_validator():
    """The knee torque declared in N*m reaches the electric_actuator validator as N*m (same unit)."""
    checks, _ = select_physics_checks(_spec(_leg_quantities()))
    act = next(c for c in checks if c.validator == "electric_actuator")
    assert act.inputs["joint_torque"] == pytest.approx(30.0)
    assert act.inputs["gear_ratio"] == pytest.approx(40.0)


def test_well_sized_leg_passes_the_gate():
    """A leg whose every axis clears its margin yields one passing δ-physics verdict."""
    result = evaluate_spec_physics(_spec(_leg_quantities(knee_torque=30.0)))
    assert result["gate"].passed
    assert result["gaps"] == []
    assert len(result["checks"]) >= 6


def test_undersized_knee_actuator_fails_honestly():
    """A 60 N·m demand exceeds the 40:1 BLDC's reflected envelope (~40.8 N·m at 3 rad/s): the gate
    FAILS — the under-sized actuator is surfaced, never masked as a pass."""
    result = evaluate_spec_physics(_spec(_leg_quantities(knee_torque=60.0)))
    assert not result["gate"].passed
    assert any("electric_actuator" in f.detail for f in result["gate"].failures)


def test_missing_motor_rating_becomes_a_gap_not_a_silent_drop():
    """The knee actuator is indicated (its torque is declared) but the motor rating is missing: an
    explicit gap, never a silently-dropped check."""
    qs = [q for q in _leg_quantities() if q.measurand != "motor.stall_torque"]
    checks, gaps = select_physics_checks(_spec(qs))
    assert all(c.validator != "electric_actuator" for c in checks)
    assert any("actuator" in g.lower() or "electric" in g.lower() for g in gaps)
