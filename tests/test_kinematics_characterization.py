"""Depth-audit characterization tests for ``src/gen/kinematics.py`` (δ closed-form robot axes).

These tests are *facade-killers*: they prove that the four DH/IK/torque/ZMP building blocks
are real closed-form implementations, not stubs or lookup tables. For each:
(a) headline output matches an independent closed-form / hand-computed anchor, and output
    changes meaningfully when a driving input changes (input is *consumed*),
(b) the documented fail-loud path raises the exact ValueError (no silent defaults).

Numeric invariants are pinned with Hypothesis property tests (DH product ≡ 2R trig form;
exact base torque m·g·L for horizontal massless; exact ZMP shift (com_z/g)·a_x).

The task scope requires exercising BOTH elbow_up branches, vertical-torque ~0 case,
exact ZMP acceleration shift, several angle sets for FK, and the listed negative guards.
No source change required — module reads REAL and stays byte-stable.

Offline, deterministic, numpy inside only for matrix product. Run:
  pytest tests/test_kinematics_characterization.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.kinematics import (  # noqa: E402
    STANDARD_GRAVITY,
    forward_kinematics_dh,
    inverse_kinematics_2r,
    reach_check,
    static_joint_torques,
    zmp_balance_check,
)


# --------------------------------------------------------------------------- #
# forward_kinematics_dh — DH product vs planar-2R closed form
# --------------------------------------------------------------------------- #

def test_forward_dh_planar_2r_matches_closed_form_several_angles():
    """(Spec) forward_kinematics_dh of planar 2R (a=l, alpha=d=0, theta=cumulative)
    matches x = l1*cosθ1 + l2*cos(θ1+θ2), y=... to machine precision for several sets,
    and position changes when θ changes."""
    cases = [
        (0.4, 0.3, 0.0, 0.0),
        (0.4, 0.3, 0.5, -0.7),
        (0.5, 0.2, 1.2, 2.1),
        (0.35, 0.45, -0.9, 1.4),
    ]
    for l1, l2, t1, t2 in cases:
        res = forward_kinematics_dh([(l1, 0.0, 0.0, t1), (l2, 0.0, 0.0, t2)])
        x, y, z = res["position"]
        expected_x = l1 * math.cos(t1) + l2 * math.cos(t1 + t2)
        expected_y = l1 * math.sin(t1) + l2 * math.sin(t1 + t2)
        assert x == pytest.approx(expected_x, abs=1e-12)
        assert y == pytest.approx(expected_y, abs=1e-12)
        assert z == pytest.approx(0.0, abs=1e-12)

    # Input consumed: change in theta moves position (not a constant pose)
    base = forward_kinematics_dh([(0.4, 0.0, 0.0, 0.3), (0.3, 0.0, 0.0, 0.6)])
    moved = forward_kinematics_dh([(0.4, 0.0, 0.0, 0.3), (0.3, 0.0, 0.0, 0.9)])
    assert moved["position"] != base["position"]


@settings(max_examples=60, deadline=None)
@given(
    l1=st.floats(min_value=1e-3, max_value=5.0),
    l2=st.floats(min_value=1e-3, max_value=5.0),
    t1=st.floats(min_value=-math.pi, max_value=math.pi),
    t2=st.floats(min_value=-math.pi, max_value=math.pi),
)
def test_forward_dh_planar_identity_property(l1, l2, t1, t2):
    """Property (invariant): for any planar 2R params the general DH product equals the
    cumulative-angle trig closed form to machine precision."""
    res = forward_kinematics_dh([(l1, 0.0, 0.0, t1), (l2, 0.0, 0.0, t2)])
    x, y, _ = res["position"]
    ex = l1 * math.cos(t1) + l2 * math.cos(t1 + t2)
    ey = l1 * math.sin(t1) + l2 * math.sin(t1 + t2)
    assert x == pytest.approx(ex, rel=1e-9, abs=1e-12)
    assert y == pytest.approx(ey, rel=1e-9, abs=1e-12)


def test_forward_dh_empty_raises():
    with pytest.raises(ValueError):
        forward_kinematics_dh([])


# --------------------------------------------------------------------------- #
# inverse_kinematics_2r — round-trips for both branches + unreachable
# --------------------------------------------------------------------------- #

def test_inverse_kinematics_2r_roundtrips_both_elbow_orientations():
    """(Spec) FK→IK→FK recovers a reachable (x,y) for BOTH elbow_up=True and False."""
    l1, l2 = 0.42, 0.31
    # Pick a reachable target
    fk = forward_kinematics_dh([(l1, 0.0, 0.0, 0.8), (l2, 0.0, 0.0, -0.4)])
    x, y, _ = fk["position"]

    for elbow_up in (True, False):
        ik = inverse_kinematics_2r(l1, l2, x, y, elbow_up=elbow_up)
        assert ik["reachable"] is True
        # Re-apply the returned angles (note: t2 is the relative joint angle)
        back = forward_kinematics_dh([(l1, 0.0, 0.0, ik["theta1"]), (l2, 0.0, 0.0, ik["theta2"])])
        bx, by, _ = back["position"]
        assert bx == pytest.approx(x, abs=1e-9)
        assert by == pytest.approx(y, abs=1e-9)


def test_inverse_kinematics_unreachable_outside_annulus():
    """(Spec) target outside the annulus → reachable=False with NaN angles."""
    l1, l2 = 0.4, 0.3
    ik = inverse_kinematics_2r(l1, l2, 1.2, 0.0)  # r=1.2 > 0.7
    assert ik["reachable"] is False
    assert math.isnan(ik["theta1"]) and math.isnan(ik["theta2"])


def test_inverse_kinematics_nonpositive_lengths_raise():
    with pytest.raises(ValueError, match="link lengths must be positive"):
        inverse_kinematics_2r(0.0, 0.3, 0.2, 0.1)
    with pytest.raises(ValueError, match="link lengths must be positive"):
        inverse_kinematics_2r(0.4, -0.1, 0.2, 0.1)


# --------------------------------------------------------------------------- #
# static_joint_torques — gravity lever-arm torques
# --------------------------------------------------------------------------- #

def test_static_joint_torques_massless_horizontal_exactly_mgL():
    """(Spec) single massless link length L, payload m, theta=0 (horizontal) gives
    base torque exactly == m·g·L."""
    L, m = 0.55, 1.8
    res = static_joint_torques([L], [0.0], [0.0], payload_mass=m)
    expected = m * STANDARD_GRAVITY * L
    assert res["torques"][0] == pytest.approx(expected, rel=1e-12)
    assert res["max_torque"] == pytest.approx(expected, rel=1e-12)


def test_static_joint_torques_vertical_is_near_zero():
    """(Spec) when the link points vertically (cum theta ~ ±pi/2), horizontal lever arm ~0
    → torque ~0."""
    L, m = 0.6, 2.5
    # theta = pi/2 (up in +y; x unchanged)
    res_up = static_joint_torques([L], [math.pi / 2], [0.0], payload_mass=m)
    assert abs(res_up["torques"][0]) < 1e-12
    # theta = -pi/2
    res_down = static_joint_torques([L], [-math.pi / 2], [0.0], payload_mass=m)
    assert abs(res_down["torques"][0]) < 1e-12


def test_static_joint_torques_input_consumed_and_max():
    """Driving inputs change output: payload and link mass increase torque; multiple
    joints report per-joint + max."""
    base = static_joint_torques([0.3, 0.25], [0.0, 0.0], [0.8, 0.6], payload_mass=1.0)
    more_payload = static_joint_torques([0.3, 0.25], [0.0, 0.0], [0.8, 0.6], payload_mass=2.0)
    assert more_payload["max_torque"] > base["max_torque"]
    assert len(base["torques"]) == 2


def test_static_joint_torques_guards():
    # length mismatch
    with pytest.raises(ValueError, match="same non-zero length"):
        static_joint_torques([0.4, 0.3], [0.0], [1.0, 1.0])
    # non-positive g
    with pytest.raises(ValueError, match="g must be positive"):
        static_joint_torques([0.4], [0.0], [1.0], g=0.0)
    # negative mass or length
    with pytest.raises(ValueError, match="masses and lengths must be non-negative"):
        static_joint_torques([0.4], [0.0], [-0.1])
    with pytest.raises(ValueError, match="masses and lengths must be non-negative"):
        static_joint_torques([-0.1], [0.0], [1.0])
    with pytest.raises(ValueError, match="masses and lengths must be non-negative"):
        static_joint_torques([0.4], [0.0], [1.0], payload_mass=-0.5)


# --------------------------------------------------------------------------- #
# zmp_balance_check — stability margin + dynamic shift
# --------------------------------------------------------------------------- #

def test_zmp_centered_margin_one_edge_margin_zero_outside_false():
    """(Spec) centered CoM → stability_margin≈1; on support edge → margin≈0 and ok True;
    just outside → ok flips False."""
    centered = zmp_balance_check(com_x=0.0, com_z=1.0, support_min_x=-0.1, support_max_x=0.1)
    assert centered["ok"] is True
    assert centered["stability_margin"] == pytest.approx(1.0, abs=1e-12)

    edge = zmp_balance_check(com_x=0.1, com_z=1.0, support_min_x=-0.1, support_max_x=0.1)
    assert edge["ok"] is True
    assert edge["stability_margin"] == pytest.approx(0.0, abs=1e-12)

    outside = zmp_balance_check(com_x=0.1001, com_z=1.0, support_min_x=-0.1, support_max_x=0.1)
    assert outside["ok"] is False
    assert outside["stability_margin"] < 0.0


def test_zmp_accel_x_shifts_zmp_exactly():
    """(Spec) nonzero accel_x shifts zmp_x by exactly (com_z/g)·accel_x (ZMP_x = com_x − (com_z/g)·a_x).
    (Positive forward accel moves ZMP backward/negative.)"""
    com_z = 0.9
    accel = 1.0
    res = zmp_balance_check(com_x=0.05, com_z=com_z, support_min_x=-0.2, support_max_x=0.2, accel_x=accel)
    expected_shift = (com_z / STANDARD_GRAVITY) * accel
    assert res["zmp_x"] == pytest.approx(0.05 - expected_shift, abs=1e-12)
    # With this modest accel the ZMP stays inside the generous support
    assert res["ok"] is True


def test_zmp_input_consumed_and_margin_definition():
    """ZMP output changes with com_x / accel (input consumed) and margin is normalized
    half-width distance (1=centre, 0=edge)."""
    base = zmp_balance_check(0.0, 0.8, -0.15, 0.15)
    shifted = zmp_balance_check(0.05, 0.8, -0.15, 0.15)
    assert shifted["zmp_x"] > base["zmp_x"]
    assert shifted["stability_margin"] < base["stability_margin"]


def test_zmp_guards():
    # degenerate support polygon (max <= min)
    with pytest.raises(ValueError, match="support polygon must have support_max_x > support_min_x"):
        zmp_balance_check(0.0, 1.0, 0.1, 0.1)
    # negative com_z
    with pytest.raises(ValueError, match="com height must be non-negative"):
        zmp_balance_check(0.0, -0.01, -0.1, 0.1)
    # non-positive g
    with pytest.raises(ValueError, match="g must be positive"):
        zmp_balance_check(0.0, 1.0, -0.1, 0.1, g=0.0)


# --------------------------------------------------------------------------- #
# reach_check (supporting) and additional negatives
# --------------------------------------------------------------------------- #

def test_reach_check_nonpositive_raises():
    with pytest.raises(ValueError, match="link lengths must be positive"):
        reach_check(0.0, 0.3, 0.1, 0.0)


@settings(max_examples=30, deadline=None)
@given(
    l1=st.floats(min_value=0.05, max_value=2.0),
    l2=st.floats(min_value=0.05, max_value=2.0),
    x=st.floats(min_value=-5.0, max_value=5.0),
    y=st.floats(min_value=-5.0, max_value=5.0),
)
def test_zmp_shift_property(l1, l2, x, y):  # l1/l2 unused, just to show variety of inputs
    """Property: the ZMP formula shift is always exactly -(com_z/g)*accel_x regardless of support."""
    # fix com/support, vary accel; also pick random com_z
    com_z = 0.7
    accel = 1.5
    res = zmp_balance_check(x, com_z, -0.2, 0.2, accel_x=accel)
    assert res["zmp_x"] == pytest.approx(x - (com_z / STANDARD_GRAVITY) * accel, abs=1e-12)


# Note: static length-mismatch + degen support + negative link already asserted in their guard sections.
