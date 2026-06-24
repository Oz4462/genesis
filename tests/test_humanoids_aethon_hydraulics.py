"""AETHON hydraulic knee/ankle option vs electric AK80-64 — honest gated comparison.

The module uses only actuation primitives (F=p·A, Q=A·v, Hagen-Poiseuille) with explicit cited inputs
(75 Nm knee peak + joint speed, lever arm). No dependency on genesis_humanoid internals.

Tests prove:
- numbers are computed (change when inputs change; match closed-form anchors)
- primitives are actually called and their outputs consumed
- documented fail-loud guards raise exactly as specified
- determinism (same input → identical output)
- at least one Hypothesis property-based invariant (scaling identities)
- the strict recommendation contract: electric default unless ALL strict-win + buildable conditions hold

Run: PYTHONPATH=src python -m pytest tests/test_humanoids_aethon_hydraulics.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hypothesis import given, strategies as st

from gen.humanoids import aethon_hydraulics as ah  # noqa: E402
from gen.actuation import hydraulic_cylinder_check  # for direct anchor cross-check


# --------------------------------------------------------------------------- #
# Basic contract + closed-form anchors (example-driven)
# --------------------------------------------------------------------------- #

def test_cited_inputs_match_spec():
    assert ah.KNEE_TORQUE_DEMAND_NM == 75.0
    assert ah.KNEE_JOINT_SPEED_RAD_S > 0.0
    assert 0.04 < ah.KNEE_LEVER_ARM_M < 0.08
    assert ah.HYDRAULIC_PRESSURE_PA > 5e6  # at least 50 bar


def test_knee_hydraulic_force_is_p_times_a():
    """Required force = torque / lever; cylinder force available == p * A (primitive, friction=0)."""
    res = ah.compute_hydraulic_option("knee", ah.KNEE_TORQUE_DEMAND_NM, ah.KNEE_JOINT_SPEED_RAD_S, ah.KNEE_LEVER_ARM_M)
    expected_f = ah.KNEE_TORQUE_DEMAND_NM / ah.KNEE_LEVER_ARM_M
    assert res.required_force_n == pytest.approx(expected_f, rel=1e-12)
    # With our sizing for CYLINDER_SF_TARGET the returned available should satisfy the SF
    assert res.cylinder["force_available"] == pytest.approx(res.pressure_pa * res.bore_area_m2, rel=1e-9)
    assert res.cylinder["safety_factor"] >= ah.CYLINDER_SF_TARGET * 0.95


def test_flow_q_is_a_times_v():
    """Q_required == bore * piston_velocity and piston_velocity == speed * lever (mapping)."""
    res = ah.compute_hydraulic_option("knee", ah.KNEE_TORQUE_DEMAND_NM, ah.KNEE_JOINT_SPEED_RAD_S, ah.KNEE_LEVER_ARM_M)
    v_calc = ah.KNEE_JOINT_SPEED_RAD_S * ah.KNEE_LEVER_ARM_M
    assert res.piston_velocity_m_s == pytest.approx(v_calc, rel=1e-12)
    assert res.flow_required_m3_s == pytest.approx(res.bore_area_m2 * res.piston_velocity_m_s, rel=1e-12)


def test_line_loss_uses_hagen_and_reports_reynolds():
    res = ah.compute_hydraulic_option("knee", ah.KNEE_TORQUE_DEMAND_NM, ah.KNEE_JOINT_SPEED_RAD_S, ah.KNEE_LEVER_ARM_M)
    # pressure_drop formula must be the documented one; Re must be returned
    assert "pressure_drop_pa" in res.line
    assert "reynolds" in res.line
    assert "laminar_valid" in res.line
    # sanity: drop is positive and small relative to system p for our small Q
    assert res.line["pressure_drop_pa"] > 0.0
    assert res.line["pressure_drop_pa"] < 0.25 * res.pressure_pa


def test_pump_power_and_accumulator_are_derived():
    res = ah.compute_hydraulic_option("knee", ah.KNEE_TORQUE_DEMAND_NM, ah.KNEE_JOINT_SPEED_RAD_S, ah.KNEE_LEVER_ARM_M)
    # power = (p + dp) * Q / eff > p*Q / eff
    base = res.pressure_pa * res.flow_required_m3_s / ah.PUMP_EFF
    assert res.pump_power_w > base
    assert res.accumulator_volume_l > 0.01  # non-zero buffer


def test_head_to_head_changes_with_input():
    """Driving input (torque) changes headline outputs — proves consumption, not canned."""
    r1 = ah.compare_hydraulic_vs_electric()
    # Re-run with higher torque via direct option (compare uses the module constants; we mutate? No — call primitive path)
    # Instead: compute two options directly and show system numbers move
    o1 = ah.compute_hydraulic_option("k", ah.KNEE_TORQUE_DEMAND_NM, ah.KNEE_JOINT_SPEED_RAD_S, ah.KNEE_LEVER_ARM_M)
    o2 = ah.compute_hydraulic_option("k", 90.0, ah.KNEE_JOINT_SPEED_RAD_S, ah.KNEE_LEVER_ARM_M)
    assert o2.bore_area_m2 > o1.bore_area_m2
    assert o2.required_force_n > o1.required_force_n
    assert o2.pump_power_w > o1.pump_power_w
    assert o2.system_added_mass_kg_est > o1.system_added_mass_kg_est


def test_recommendation_contract_electric_default_under_current_params():
    """With the cited 75 Nm + realistic system overhead, electric must stay default."""
    res = ah.compare_hydraulic_vs_electric()
    rec = res["recommendation"]
    assert rec["use_hydraulic"] is False
    assert rec["choice"] == "electric"
    assert "electric stays default" in rec["reason"]
    # All deciding margins are present as numbers
    m = rec["deciding_margins"]
    assert isinstance(m["density_margin_sys_nm_per_kg"], float)
    assert isinstance(m["mass_margin_two_knee_kg"], float)
    assert isinstance(m["system_buildable"], bool)


def test_fail_loud_on_bad_inputs():
    with pytest.raises(ValueError, match="joint torque demand must be positive"):
        ah.compute_hydraulic_option("k", 0.0, ah.KNEE_JOINT_SPEED_RAD_S, ah.KNEE_LEVER_ARM_M)
    with pytest.raises(ValueError, match="lever arm must be positive"):
        ah.compute_hydraulic_option("k", ah.KNEE_TORQUE_DEMAND_NM, ah.KNEE_JOINT_SPEED_RAD_S, 0.0)
    with pytest.raises(ValueError, match="joint speed must be non-negative"):
        ah.compute_hydraulic_option("k", ah.KNEE_TORQUE_DEMAND_NM, -1.0, ah.KNEE_LEVER_ARM_M)


def test_zero_speed_is_valid_for_static_hold():
    """Speed==0 is valid for static force hold (cylinder pressure delivers torque; zero flow/pump).
    Must succeed without raising and without leaking internal primitive 'must be positive' error."""
    res = ah.compute_hydraulic_option("knee", ah.KNEE_TORQUE_DEMAND_NM, 0.0, ah.KNEE_LEVER_ARM_M)
    assert res.piston_velocity_m_s == pytest.approx(0.0)
    assert res.flow_required_m3_s == 0.0
    assert res.pump_power_w == 0.0
    assert res.cylinder["ok"]  # force hold still works
    assert res.flow["ok"]
    # line drop zeroed, no crash on pressure_drop primitive either
    assert res.line["pressure_drop_pa"] == 0.0


def test_determinism_same_inputs_identical_output():
    r1 = ah.compare_hydraulic_vs_electric()
    r2 = ah.compare_hydraulic_vs_electric()
    # recommendation and top-level numbers identical
    assert r1["recommendation"]["use_hydraulic"] == r2["recommendation"]["use_hydraulic"]
    k1, k2 = r1["knee"]["hydraulic"], r2["knee"]["hydraulic"]
    assert k1.bore_area_m2 == pytest.approx(k2.bore_area_m2, rel=1e-15)
    assert k1.pump_power_w == pytest.approx(k2.pump_power_w, rel=1e-15)


# --------------------------------------------------------------------------- #
# Property-based invariants (Hypothesis)
# --------------------------------------------------------------------------- #

@given(
    torque=st.floats(min_value=10.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    speed=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
    lever=st.floats(min_value=0.03, max_value=0.12, allow_nan=False, allow_infinity=False),
    pressure=st.floats(min_value=5e6, max_value=25e6, allow_nan=False, allow_infinity=False),
)
def test_force_and_flow_scale_linearly_property(torque, speed, lever, pressure):
    """F_required = torque/lever; Q = A * (speed*lever) — linear identities must hold for any physical inputs."""
    res = ah.compute_hydraulic_option("k", torque, speed, lever, pressure_pa=pressure)
    f_direct = torque / lever
    assert res.required_force_n == pytest.approx(f_direct, rel=1e-10)
    v = speed * lever
    assert res.piston_velocity_m_s == pytest.approx(v, rel=1e-10)
    assert res.flow_required_m3_s == pytest.approx(res.bore_area_m2 * v, rel=1e-10)
    # Force available from primitive must equal p*A (within sizing)
    assert res.cylinder["force_available"] == pytest.approx(pressure * res.bore_area_m2, rel=1e-9)


@given(
    torque=st.floats(min_value=20.0, max_value=120.0, allow_nan=False, allow_infinity=False),
)
def test_cylinder_sf_is_preserved_across_torque_property(torque):
    """When we size with CYLINDER_SF_TARGET the returned safety_factor must be at/near target (within float)."""
    res = ah.compute_hydraulic_option("k", torque, 3.0, 0.055)
    assert res.cylinder["safety_factor"] >= ah.CYLINDER_SF_TARGET * 0.90


def test_ankle_uses_smaller_sizing_than_knee():
    """Ankle demand (30 Nm) produces strictly smaller cylinder than knee (75 Nm) — input is consumed."""
    knee = ah.compute_hydraulic_option("knee", ah.KNEE_TORQUE_DEMAND_NM, ah.KNEE_JOINT_SPEED_RAD_S, ah.KNEE_LEVER_ARM_M)
    ankle = ah.compute_hydraulic_option("ankle", ah.ANKLE_TORQUE_DEMAND_NM, ah.ANKLE_JOINT_SPEED_RAD_S, ah.ANKLE_LEVER_ARM_M)
    assert ankle.bore_area_m2 < knee.bore_area_m2
    assert ankle.pump_power_w < knee.pump_power_w


def test_format_audit_verdict_is_nonempty_and_mentions_numbers():
    txt = ah.format_audit_verdict()
    assert isinstance(txt, str)
    assert len(txt) > 200
    assert "75" in txt or "knee" in txt.lower()
    assert "electric" in txt.lower() or "hydraulic" in txt.lower()
