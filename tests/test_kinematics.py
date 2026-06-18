"""Kinematics validators — DH forward, analytic 2R inverse, static joint torque, ZMP balance.

Exact anchors, not vibes: the general DH product equals the planar 2R closed form to machine
precision; FK→IK→FK round-trips; a massless link of length L holding payload m horizontally needs
exactly τ = m·g·L at the base; a target beyond l₁+l₂ is unreachable; a CoM over the foot centre is
balanced (margin 1) and one past the edge tips (ok=False); a forward CoM acceleration shifts the
ZMP backward. Every nonsense input raises.

Offline, no LLM. Run:  pytest tests/test_kinematics.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.kinematics import (  # noqa: E402
    STANDARD_GRAVITY,
    forward_kinematics_dh,
    inverse_kinematics_2r,
    reach_check,
    static_joint_torques,
    zmp_balance_check,
)


def test_dh_product_equals_the_planar_2r_closed_form():
    """The general DH product for a 2R arm (α=d=0) reproduces x=l₁cosθ₁+l₂cos(θ₁+θ₂),
    y=l₁sinθ₁+l₂sin(θ₁+θ₂) to machine precision."""
    l1, l2, t1, t2 = 0.4, 0.3, 0.5, -0.7
    res = forward_kinematics_dh([(l1, 0.0, 0.0, t1), (l2, 0.0, 0.0, t2)])
    x, y, z = res["position"]
    assert x == pytest.approx(l1 * math.cos(t1) + l2 * math.cos(t1 + t2), abs=1e-12)
    assert y == pytest.approx(l1 * math.sin(t1) + l2 * math.sin(t1 + t2), abs=1e-12)
    assert z == pytest.approx(0.0, abs=1e-12)


def test_inverse_kinematics_round_trips_through_forward():
    """IK recovers angles whose forward map lands on the requested target (FK→IK→FK is exact)."""
    l1, l2 = 0.4, 0.3
    target_t1, target_t2 = 0.6, 0.8
    fk = forward_kinematics_dh([(l1, 0.0, 0.0, target_t1), (l2, 0.0, 0.0, target_t2)])
    x, y, _ = fk["position"]
    ik = inverse_kinematics_2r(l1, l2, x, y, elbow_up=True)
    assert ik["reachable"]
    # rebuild with the IK angles directly (theta2 is relative to link 1)
    back = forward_kinematics_dh([(l1, 0.0, 0.0, ik["theta1"]), (l2, 0.0, 0.0, ik["theta2"])])
    bx, by, _ = back["position"]
    assert bx == pytest.approx(x, abs=1e-9)
    assert by == pytest.approx(y, abs=1e-9)


def test_target_beyond_reach_is_unreachable():
    """A point past l₁+l₂ cannot be reached — IK reports it instead of returning a wrong angle."""
    ik = inverse_kinematics_2r(0.4, 0.3, 1.0, 0.0)
    assert not ik["reachable"]
    assert math.isnan(ik["theta1"]) and math.isnan(ik["theta2"])


def test_static_base_torque_is_payload_times_gravity_times_reach():
    """A massless link of length L holding payload m horizontally needs exactly τ = m·g·L."""
    L, m = 0.5, 2.0
    res = static_joint_torques([L], [0.0], [0.0], payload_mass=m)
    assert res["torques"][0] == pytest.approx(m * STANDARD_GRAVITY * L, rel=1e-12)


def test_static_torque_accounts_for_link_mass_and_multiple_joints():
    """Two horizontal links with their own mass + a tip payload: each joint holds the gravity
    torque of every distal mass at its horizontal lever arm."""
    g = STANDARD_GRAVITY
    res = static_joint_torques([0.3, 0.3], [0.0, 0.0], [1.0, 1.0], payload_mass=2.0)
    # joint0 at x=0: links' CoM at 0.15 and 0.45, payload at 0.6
    assert res["torques"][0] == pytest.approx(g * (1.0 * 0.15 + 1.0 * 0.45 + 2.0 * 0.6), rel=1e-12)
    # joint1 at x=0.3: only link1 (CoM 0.45) + payload (0.6) are distal
    assert res["torques"][1] == pytest.approx(g * (1.0 * 0.15 + 2.0 * 0.3), rel=1e-12)
    assert res["max_torque"] == pytest.approx(res["torques"][0], rel=1e-12)


def test_reach_check_inside_and_outside_the_workspace():
    inside = reach_check(0.4, 0.3, 0.5, 0.0)          # r=0.5, annulus [0.1, 0.7]
    assert inside["ok"] and inside["safety_factor"] > 1.0
    outside = reach_check(0.4, 0.3, 1.0, 0.0)          # r=1.0 > 0.7
    assert not outside["ok"]


def test_zmp_centered_is_balanced_edge_is_marginal_outside_tips():
    centered = zmp_balance_check(com_x=0.0, com_z=1.0, support_min_x=-0.1, support_max_x=0.1)
    assert centered["ok"] and centered["stability_margin"] == pytest.approx(1.0, abs=1e-12)
    edge = zmp_balance_check(com_x=0.1, com_z=1.0, support_min_x=-0.1, support_max_x=0.1)
    assert edge["ok"] and edge["stability_margin"] == pytest.approx(0.0, abs=1e-12)
    outside = zmp_balance_check(com_x=0.2, com_z=1.0, support_min_x=-0.1, support_max_x=0.1)
    assert not outside["ok"] and outside["stability_margin"] < 0.0


def test_zmp_shifts_with_horizontal_acceleration():
    """A forward CoM acceleration moves the ZMP backward: ZMP_x = com_x − (com_z/g)·a_x."""
    res = zmp_balance_check(com_x=0.0, com_z=1.0, support_min_x=-0.1, support_max_x=0.1,
                            accel_x=STANDARD_GRAVITY)
    assert res["zmp_x"] == pytest.approx(-1.0, abs=1e-12)   # 0 − (1.0/g)·g
    assert not res["ok"]


def test_folded_singularity_returns_a_valid_branch():
    """At the fully-folded singularity (l₁=l₂, target at the origin) θ₁ is geometrically
    indeterminate; the IK returns one valid branch (not NaN) whose forward kinematics still lands on
    the origin — the singularity is handled, not silently wrong."""
    ik = inverse_kinematics_2r(0.3, 0.3, 0.0, 0.0)
    assert ik["reachable"]
    assert not math.isnan(ik["theta1"]) and not math.isnan(ik["theta2"])
    fk = forward_kinematics_dh([(0.3, 0.0, 0.0, ik["theta1"]), (0.3, 0.0, 0.0, ik["theta2"])])
    assert fk["position"][0] == pytest.approx(0.0, abs=1e-9)
    assert fk["position"][1] == pytest.approx(0.0, abs=1e-9)


def test_nonsense_inputs_raise():
    with pytest.raises(ValueError):
        forward_kinematics_dh([])
    with pytest.raises(ValueError):
        inverse_kinematics_2r(-0.4, 0.3, 0.5, 0.0)
    with pytest.raises(ValueError):
        static_joint_torques([0.5], [0.0], [1.0, 2.0])      # length mismatch
    with pytest.raises(ValueError):
        zmp_balance_check(com_x=0.0, com_z=1.0, support_min_x=0.1, support_max_x=-0.1)  # degenerate
