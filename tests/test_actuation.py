"""Actuation validators — electric motor+gear torque–speed, hydraulic force/flow/line-loss.

Exact anchors, not vibes: a 0.5 N·m motor through a 25:1 gear at 80 % efficiency delivers exactly
10 N·m at the joint (and 12 rad/s no-load); the envelope halves the torque at half the max speed;
overspeed fails honestly; 200 bar on a 0.001 m² bore is exactly 20 kN (F = p·A); a 0.001 m² piston
at 0.1 m/s needs exactly 1e-4 m³/s (Q = A·v); Hagen–Poiseuille Δp matches 128·μ·L·Q/(π·d⁴) and flags
turbulent flow instead of applying the laminar formula blindly. Every nonsense input raises.

Offline, no LLM. Run:  pytest tests/test_actuation.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.actuation import (  # noqa: E402
    electric_actuator_check,
    hydraulic_cylinder_check,
    hydraulic_flow_check,
    hydraulic_pressure_drop,
)


def test_electric_static_torque_is_stall_times_gear_times_efficiency():
    """At zero speed the joint torque is exactly τ_stall·N·η; demanding that much gives safety 1.0."""
    res = electric_actuator_check(joint_torque=10.0, joint_speed=0.0, motor_stall_torque=0.5,
                                  motor_noload_speed=300.0, gear_ratio=25.0, efficiency=0.8)
    assert res["max_joint_torque"] == pytest.approx(0.5 * 25.0 * 0.8, rel=1e-12)   # 10 N·m
    assert res["max_joint_speed"] == pytest.approx(300.0 / 25.0, rel=1e-12)         # 12 rad/s
    assert res["safety_factor"] == pytest.approx(1.0, rel=1e-12)
    assert res["ok"]


def test_electric_torque_falls_linearly_with_speed():
    """At half the max joint speed the available torque is half the stall torque (linear envelope)."""
    res = electric_actuator_check(joint_torque=2.5, joint_speed=6.0, motor_stall_torque=0.5,
                                  motor_noload_speed=300.0, gear_ratio=25.0, efficiency=0.8)
    assert res["available_torque"] == pytest.approx(5.0, rel=1e-12)   # 10·(1 − 6/12)
    assert res["safety_factor"] == pytest.approx(2.0, rel=1e-12)
    assert res["ok"]


def test_electric_overspeed_fails_honestly():
    """Past the no-load joint speed the motor delivers no torque — the design is a clean fail."""
    res = electric_actuator_check(joint_torque=1.0, joint_speed=15.0, motor_stall_torque=0.5,
                                  motor_noload_speed=300.0, gear_ratio=25.0, efficiency=0.8)
    assert not res["ok"]                       # 15 rad/s > 12 rad/s max
    assert res["available_torque"] < 0.0


def test_hydraulic_cylinder_force_is_pressure_times_area():
    """200 bar across a 0.001 m² bore is exactly 20 kN (F = p·A), minus declared friction."""
    res = hydraulic_cylinder_check(pressure=200e5, bore_area=0.001, required_force=1.0)
    assert res["force_available"] == pytest.approx(20000.0, rel=1e-12)
    strong = hydraulic_cylinder_check(pressure=200e5, bore_area=0.001, required_force=15000.0)
    assert strong["ok"] and strong["safety_factor"] == pytest.approx(20000.0 / 15000.0, rel=1e-12)
    weak = hydraulic_cylinder_check(pressure=200e5, bore_area=0.001, required_force=25000.0)
    assert not weak["ok"]
    with_friction = hydraulic_cylinder_check(pressure=200e5, bore_area=0.001, required_force=1.0,
                                             friction=5000.0)
    assert with_friction["force_available"] == pytest.approx(15000.0, rel=1e-12)


def test_hydraulic_flow_is_area_times_velocity():
    """A 0.001 m² piston at 0.1 m/s needs exactly 1e-4 m³/s; a 1.5e-4 pump clears it (safety 1.5)."""
    res = hydraulic_flow_check(bore_area=0.001, piston_velocity=0.1, pump_flow=1.5e-4)
    assert res["flow_required"] == pytest.approx(1e-4, rel=1e-12)
    assert res["safety_factor"] == pytest.approx(1.5, rel=1e-12)
    assert res["ok"]


def test_pressure_drop_matches_hagen_poiseuille_and_flags_turbulence():
    """Δp = 128·μ·L·Q/(π·d⁴) exactly; a high-Reynolds flow is flagged non-laminar, not faked."""
    q, d, length, mu, rho = 1e-4, 0.01, 1.0, 0.03, 870.0
    res = hydraulic_pressure_drop(flow=q, diameter=d, length=length, viscosity=mu, density=rho)
    assert res["pressure_drop_pa"] == pytest.approx(128.0 * mu * length * q / (math.pi * d**4), rel=1e-12)
    assert res["reynolds"] == pytest.approx(4.0 * rho * q / (math.pi * d * mu), rel=1e-12)
    assert res["laminar_valid"]                                   # Re ≈ 369 < 2300
    turbulent = hydraulic_pressure_drop(flow=1e-2, diameter=d, length=length, viscosity=mu, density=rho)
    assert not turbulent["laminar_valid"]                        # Re ≈ 3.7e4


def test_nonsense_inputs_raise():
    with pytest.raises(ValueError):
        electric_actuator_check(1.0, 0.0, -0.5, 300.0, 25.0)         # negative stall torque
    with pytest.raises(ValueError):
        electric_actuator_check(1.0, 0.0, 0.5, 300.0, 25.0, efficiency=1.5)  # efficiency > 1
    with pytest.raises(ValueError):
        hydraulic_cylinder_check(pressure=-1.0, bore_area=0.001, required_force=1.0)
    with pytest.raises(ValueError):
        hydraulic_flow_check(bore_area=0.001, piston_velocity=-0.1, pump_flow=1e-4)
    with pytest.raises(ValueError):
        hydraulic_pressure_drop(flow=1e-4, diameter=0.0, length=1.0, viscosity=0.03)
