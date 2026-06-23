"""Characterization + depth-audit tests for ``gen.actuation`` — prove the closed forms are
COMPUTED, not canned.

Every assertion below either (a) pins an output against an independently hand-computed anchor, or
(b) shows the output MOVES meaningfully when a driving input moves (so no field is a hidden
constant), or (c) exercises a documented fail-loud guard. Property-based tests (Hypothesis) pin the
math identities themselves across the whole input space — τ_stall·N·η, the linear envelope,
F = p·A − friction, Q = A·v, Hagen–Poiseuille Δp and the Reynolds number — so a regression in any
formula cannot hide behind a few lucky example points.

This is the audit's executable verdict: ``actuation.py`` reads REAL on inspection and stays
unedited. Offline, no LLM. Run:  pytest tests/test_actuation_characterization.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.actuation import (  # noqa: E402
    electric_actuator_check,
    hydraulic_cylinder_check,
    hydraulic_flow_check,
    hydraulic_pressure_drop,
)


# --------------------------------------------------------------------------------------------------
# electric_actuator_check
# --------------------------------------------------------------------------------------------------

def test_electric_anchor_max_torque_speed_envelope_and_safety():
    """Hand-computed anchor: stall 0.4, N=20, η=0.9 → max_torque = 0.4·20·0.9 = 7.2 N·m;
    no-load 200 → max_speed = 200/20 = 10 rad/s; at ω=4 the envelope is 7.2·(1−4/10) = 4.32 N·m;
    demanding 2.16 N·m gives safety_factor exactly 2.0 and ok True."""
    res = electric_actuator_check(joint_torque=2.16, joint_speed=4.0, motor_stall_torque=0.4,
                                  motor_noload_speed=200.0, gear_ratio=20.0, efficiency=0.9)
    assert res["max_joint_torque"] == pytest.approx(7.2, rel=1e-12)
    assert res["max_joint_speed"] == pytest.approx(10.0, rel=1e-12)
    assert res["available_torque"] == pytest.approx(4.32, rel=1e-12)   # 7.2·(1 − 4/10)
    assert res["safety_factor"] == pytest.approx(2.0, rel=1e-12)       # 4.32 / 2.16
    assert res["ok"]


def test_electric_safety_factor_is_available_over_demand():
    """safety_factor == available_torque / joint_torque (not stall/demand, not max/demand)."""
    res = electric_actuator_check(joint_torque=3.0, joint_speed=5.0, motor_stall_torque=0.5,
                                  motor_noload_speed=300.0, gear_ratio=25.0, efficiency=0.8)
    assert res["safety_factor"] == pytest.approx(res["available_torque"] / 3.0, rel=1e-12)


def test_electric_safety_factor_is_inf_at_zero_demand():
    """Zero torque demand is a meaningful evaluable case → infinite safety, not a div-by-zero crash."""
    res = electric_actuator_check(joint_torque=0.0, joint_speed=2.0, motor_stall_torque=0.5,
                                  motor_noload_speed=300.0, gear_ratio=25.0, efficiency=0.8)
    assert res["safety_factor"] == float("inf")
    assert res["ok"]                              # 0 ≤ available, 2 ≤ 12 max speed


def test_electric_fails_when_demand_exceeds_envelope():
    """A torque demand above the speed-derated envelope is a clean fail (ok False, safety < 1)."""
    res = electric_actuator_check(joint_torque=6.0, joint_speed=6.0, motor_stall_torque=0.5,
                                  motor_noload_speed=300.0, gear_ratio=25.0, efficiency=0.8)
    # envelope at 6 rad/s: 10·(1 − 6/12) = 5 N·m < 6 demanded
    assert res["available_torque"] == pytest.approx(5.0, rel=1e-12)
    assert not res["ok"]
    assert res["safety_factor"] < 1.0


def test_electric_fails_when_speed_exceeds_max_even_if_torque_small():
    """Overspeed alone fails: past no-load joint speed the envelope torque goes negative."""
    res = electric_actuator_check(joint_torque=0.1, joint_speed=15.0, motor_stall_torque=0.5,
                                  motor_noload_speed=300.0, gear_ratio=25.0, efficiency=0.8)
    assert res["max_joint_speed"] == pytest.approx(12.0, rel=1e-12)
    assert not res["ok"]                          # 15 > 12 rad/s
    assert res["available_torque"] < 0.0


def test_electric_output_moves_with_gear_ratio_efficiency_and_demand():
    """No field is a hidden constant: changing gear_ratio, efficiency, or demand each moves output."""
    base = electric_actuator_check(2.0, 3.0, 0.5, 300.0, 25.0, 0.8)
    more_gear = electric_actuator_check(2.0, 3.0, 0.5, 300.0, 30.0, 0.8)
    more_eff = electric_actuator_check(2.0, 3.0, 0.5, 300.0, 25.0, 0.95)
    more_demand = electric_actuator_check(4.0, 3.0, 0.5, 300.0, 25.0, 0.8)

    # higher reduction → more joint torque but LESS joint speed (the trade-off is real, not faked)
    assert more_gear["max_joint_torque"] > base["max_joint_torque"]
    assert more_gear["max_joint_speed"] < base["max_joint_speed"]
    # higher efficiency → more available torque, higher safety
    assert more_eff["max_joint_torque"] > base["max_joint_torque"]
    assert more_eff["safety_factor"] > base["safety_factor"]
    # higher torque demand → lower safety, same envelope
    assert more_demand["safety_factor"] < base["safety_factor"]
    assert more_demand["available_torque"] == pytest.approx(base["available_torque"], rel=1e-12)


@pytest.mark.parametrize("kwargs", [
    dict(joint_torque=1.0, joint_speed=0.0, motor_stall_torque=-0.5, motor_noload_speed=300.0, gear_ratio=25.0),
    dict(joint_torque=1.0, joint_speed=0.0, motor_stall_torque=0.5, motor_noload_speed=0.0, gear_ratio=25.0),
    dict(joint_torque=1.0, joint_speed=0.0, motor_stall_torque=0.5, motor_noload_speed=300.0, gear_ratio=0.0),
    dict(joint_torque=1.0, joint_speed=0.0, motor_stall_torque=0.5, motor_noload_speed=300.0, gear_ratio=25.0, efficiency=0.0),
    dict(joint_torque=1.0, joint_speed=0.0, motor_stall_torque=0.5, motor_noload_speed=300.0, gear_ratio=25.0, efficiency=1.5),
    dict(joint_torque=-1.0, joint_speed=0.0, motor_stall_torque=0.5, motor_noload_speed=300.0, gear_ratio=25.0),
    dict(joint_torque=1.0, joint_speed=-2.0, motor_stall_torque=0.5, motor_noload_speed=300.0, gear_ratio=25.0),
])
def test_electric_guards_raise(kwargs):
    """Non-positive ratings/gear, efficiency outside (0,1], or negative demand fail loud."""
    with pytest.raises(ValueError):
        electric_actuator_check(**kwargs)


def test_electric_efficiency_boundary_one_is_allowed():
    """η == 1.0 is the lossless boundary and must be accepted (interval is (0, 1])."""
    res = electric_actuator_check(1.0, 0.0, 0.5, 300.0, 25.0, efficiency=1.0)
    assert res["max_joint_torque"] == pytest.approx(0.5 * 25.0, rel=1e-12)


@settings(max_examples=200)
@given(
    stall=st.floats(min_value=1e-3, max_value=1e3),
    noload=st.floats(min_value=1e-2, max_value=1e4),
    gear=st.floats(min_value=1e-2, max_value=1e3),
    eff=st.floats(min_value=1e-3, max_value=1.0),
    speed_frac=st.floats(min_value=0.0, max_value=2.0),   # span both under- and over-speed
)
def test_electric_envelope_identity_property(stall, noload, gear, eff, speed_frac):
    """For ALL valid inputs: max_torque = stall·N·η, max_speed = noload/N, and the available torque
    is exactly the linear envelope max_torque·(1 − ω/max_speed)."""
    max_speed = noload / gear
    speed = speed_frac * max_speed
    res = electric_actuator_check(joint_torque=1.0, joint_speed=speed, motor_stall_torque=stall,
                                  motor_noload_speed=noload, gear_ratio=gear, efficiency=eff)
    assert res["max_joint_torque"] == pytest.approx(stall * gear * eff, rel=1e-9)
    assert res["max_joint_speed"] == pytest.approx(max_speed, rel=1e-9)
    expected = (stall * gear * eff) * (1.0 - speed / max_speed)
    assert res["available_torque"] == pytest.approx(expected, rel=1e-9, abs=1e-12)


# --------------------------------------------------------------------------------------------------
# hydraulic_cylinder_check
# --------------------------------------------------------------------------------------------------

def test_hydraulic_cylinder_anchor_force_minus_friction():
    """150 bar (1.5e7 Pa) across 0.002 m² → 30 kN ideal; minus 2 kN friction → 28 kN available."""
    res = hydraulic_cylinder_check(pressure=1.5e7, bore_area=0.002, required_force=14000.0,
                                   friction=2000.0)
    assert res["force_available"] == pytest.approx(28000.0, rel=1e-12)   # 1.5e7·0.002 − 2000
    assert res["safety_factor"] == pytest.approx(2.0, rel=1e-12)         # 28000 / 14000
    assert res["ok"]


def test_hydraulic_cylinder_output_moves_with_pressure_area_friction():
    """Force tracks p and A up, friction down — none is a hidden constant."""
    base = hydraulic_cylinder_check(1.0e7, 0.001, 1.0)
    assert hydraulic_cylinder_check(2.0e7, 0.001, 1.0)["force_available"] > base["force_available"]
    assert hydraulic_cylinder_check(1.0e7, 0.002, 1.0)["force_available"] > base["force_available"]
    assert hydraulic_cylinder_check(1.0e7, 0.001, 1.0, friction=5000.0)["force_available"] < base["force_available"]


@pytest.mark.parametrize("kwargs", [
    dict(pressure=0.0, bore_area=0.001, required_force=1.0),
    dict(pressure=-1.0, bore_area=0.001, required_force=1.0),
    dict(pressure=1e7, bore_area=0.0, required_force=1.0),
    dict(pressure=1e7, bore_area=0.001, required_force=0.0),
    dict(pressure=1e7, bore_area=0.001, required_force=-5.0),
    dict(pressure=1e7, bore_area=0.001, required_force=1.0, friction=-1.0),
])
def test_hydraulic_cylinder_guards_raise(kwargs):
    with pytest.raises(ValueError):
        hydraulic_cylinder_check(**kwargs)


@settings(max_examples=150)
@given(
    pressure=st.floats(min_value=1e3, max_value=1e9),
    area=st.floats(min_value=1e-6, max_value=1.0),
    friction=st.floats(min_value=0.0, max_value=1e5),
)
def test_hydraulic_cylinder_force_identity_property(pressure, area, friction):
    """F_available = p·A − friction for ALL valid inputs."""
    res = hydraulic_cylinder_check(pressure=pressure, bore_area=area, required_force=1.0,
                                   friction=friction)
    assert res["force_available"] == pytest.approx(pressure * area - friction, rel=1e-9, abs=1e-9)


# --------------------------------------------------------------------------------------------------
# hydraulic_flow_check
# --------------------------------------------------------------------------------------------------

def test_hydraulic_flow_anchor_area_times_velocity():
    """0.002 m² at 0.05 m/s needs 1e-4 m³/s; a 3e-4 pump clears it (safety 3.0)."""
    res = hydraulic_flow_check(bore_area=0.002, piston_velocity=0.05, pump_flow=3e-4)
    assert res["flow_required"] == pytest.approx(1e-4, rel=1e-12)
    assert res["safety_factor"] == pytest.approx(3.0, rel=1e-12)
    assert res["ok"]


def test_hydraulic_flow_fails_when_pump_undersized():
    """A pump below the required flow is a clean fail."""
    res = hydraulic_flow_check(bore_area=0.002, piston_velocity=0.1, pump_flow=1e-4)
    assert res["flow_required"] == pytest.approx(2e-4, rel=1e-12)
    assert not res["ok"]
    assert res["safety_factor"] < 1.0


@pytest.mark.parametrize("kwargs", [
    dict(bore_area=0.0, piston_velocity=0.1, pump_flow=1e-4),
    dict(bore_area=0.001, piston_velocity=0.0, pump_flow=1e-4),
    dict(bore_area=0.001, piston_velocity=-0.1, pump_flow=1e-4),
    dict(bore_area=0.001, piston_velocity=0.1, pump_flow=0.0),
])
def test_hydraulic_flow_guards_raise(kwargs):
    with pytest.raises(ValueError):
        hydraulic_flow_check(**kwargs)


@settings(max_examples=150)
@given(
    area=st.floats(min_value=1e-6, max_value=1.0),
    velocity=st.floats(min_value=1e-4, max_value=10.0),
    pump=st.floats(min_value=1e-6, max_value=1.0),
)
def test_hydraulic_flow_identity_property(area, velocity, pump):
    """Q_required = A·v for ALL valid inputs."""
    res = hydraulic_flow_check(bore_area=area, piston_velocity=velocity, pump_flow=pump)
    assert res["flow_required"] == pytest.approx(area * velocity, rel=1e-9, abs=1e-15)


# --------------------------------------------------------------------------------------------------
# hydraulic_pressure_drop
# --------------------------------------------------------------------------------------------------

def test_pressure_drop_anchor_hagen_poiseuille_and_reynolds():
    """Δp = 128·μ·L·Q/(π·d⁴) and Re = 4ρQ/(π·d·μ) against a fully hand-computed anchor; laminar."""
    q, d, length, mu, rho = 1e-4, 0.01, 1.0, 0.03, 870.0
    res = hydraulic_pressure_drop(flow=q, diameter=d, length=length, viscosity=mu, density=rho)
    expected_dp = 128.0 * mu * length * q / (math.pi * d**4)
    expected_re = 4.0 * rho * q / (math.pi * d * mu)
    assert res["pressure_drop_pa"] == pytest.approx(expected_dp, rel=1e-12)
    assert res["reynolds"] == pytest.approx(expected_re, rel=1e-12)
    assert expected_re < 2300.0 and res["laminar_valid"]            # Re ≈ 369


def test_pressure_drop_flags_turbulent_flow_instead_of_faking_it():
    """A high-Reynolds flow (Re > 2300) is honestly flagged non-laminar, not silently 'valid'."""
    q, d, length, mu, rho = 1e-2, 0.01, 1.0, 0.03, 870.0
    res = hydraulic_pressure_drop(flow=q, diameter=d, length=length, viscosity=mu, density=rho)
    assert res["reynolds"] > 2300.0                                 # Re ≈ 3.7e4
    assert not res["laminar_valid"]


def test_pressure_drop_output_moves_with_each_driver():
    """Δp ∝ Q, ∝ L, ∝ μ, ∝ 1/d⁴; Re ∝ Q, ∝ ρ, ∝ 1/d, ∝ 1/μ — every input genuinely drives output."""
    base = hydraulic_pressure_drop(flow=1e-4, diameter=0.01, length=1.0, viscosity=0.03)
    assert hydraulic_pressure_drop(2e-4, 0.01, 1.0, 0.03)["pressure_drop_pa"] > base["pressure_drop_pa"]
    assert hydraulic_pressure_drop(1e-4, 0.02, 1.0, 0.03)["pressure_drop_pa"] < base["pressure_drop_pa"]
    assert hydraulic_pressure_drop(1e-4, 0.01, 2.0, 0.03)["pressure_drop_pa"] > base["pressure_drop_pa"]
    # density only moves Reynolds, not the drop
    denser = hydraulic_pressure_drop(1e-4, 0.01, 1.0, 0.03, density=1000.0)
    assert denser["reynolds"] > base["reynolds"]
    assert denser["pressure_drop_pa"] == pytest.approx(base["pressure_drop_pa"], rel=1e-12)


def test_pressure_drop_quartic_diameter_dependence():
    """Halving the diameter raises Δp by exactly 2⁴ = 16× (the π·d⁴ denominator is real)."""
    wide = hydraulic_pressure_drop(flow=1e-4, diameter=0.02, length=1.0, viscosity=0.03)
    narrow = hydraulic_pressure_drop(flow=1e-4, diameter=0.01, length=1.0, viscosity=0.03)
    assert narrow["pressure_drop_pa"] == pytest.approx(16.0 * wide["pressure_drop_pa"], rel=1e-12)


@pytest.mark.parametrize("kwargs", [
    dict(flow=0.0, diameter=0.01, length=1.0, viscosity=0.03),
    dict(flow=1e-4, diameter=0.0, length=1.0, viscosity=0.03),
    dict(flow=1e-4, diameter=0.01, length=0.0, viscosity=0.03),
    dict(flow=1e-4, diameter=0.01, length=1.0, viscosity=0.0),
    dict(flow=1e-4, diameter=0.01, length=1.0, viscosity=0.03, density=0.0),
    dict(flow=-1e-4, diameter=0.01, length=1.0, viscosity=0.03),
])
def test_pressure_drop_guards_raise(kwargs):
    with pytest.raises(ValueError):
        hydraulic_pressure_drop(**kwargs)


@settings(max_examples=150)
@given(
    q=st.floats(min_value=1e-7, max_value=1e-1),
    d=st.floats(min_value=1e-3, max_value=1e-1),
    length=st.floats(min_value=1e-2, max_value=1e2),
    mu=st.floats(min_value=1e-4, max_value=1.0),
    rho=st.floats(min_value=1.0, max_value=2e3),
)
def test_pressure_drop_identities_and_flag_property(q, d, length, mu, rho):
    """Δp, Re identities hold and laminar_valid is EXACTLY (Re < 2300) for ALL valid inputs."""
    res = hydraulic_pressure_drop(flow=q, diameter=d, length=length, viscosity=mu, density=rho)
    expected_dp = 128.0 * mu * length * q / (math.pi * d**4)
    expected_re = 4.0 * rho * q / (math.pi * d * mu)
    assert res["pressure_drop_pa"] == pytest.approx(expected_dp, rel=1e-9)
    assert res["reynolds"] == pytest.approx(expected_re, rel=1e-9)
    assert res["laminar_valid"] == (expected_re < 2300.0)
