"""Humanoid scaling laws + parser torque-extraction + the knee-torque CALIBRATION FIX.

Exact checks, not vibes:
  * the extended parser reads real per-joint torque limits from all three conventions the library uses
    (URDF <limit effort>, MJCF joint actuatorfrcrange, MJCF <motor> ctrlrange×gear) and gates the
    placeholder SENTINELS (iCub effort=50000, ergoCub 1e9) to an honest None — the NEGATIVE test;
  * the discovered knee law τ = k·m·g·L_leg validates out-of-sample (LOO R² ≥ the keep bar) and the
    rejected mass-vs-height law does NOT — the discovery discipline (keep only what generalises);
  * AETHON's own knee sits inside the real-fleet band — our design is sane by the real-robot law;
  * the calibration fix: GENESIS no longer flags shipping production robots (Apollo/TALOS/H1-2) as
    unable to hold their own weight (the pre-fix false positive), and the knee model itself is the
    physically-grounded squat hold.

Offline, numpy only (the discovery/kinematics deps). Run: pytest tests/test_humanoids_scaling_laws.py
"""

from __future__ import annotations

import math
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.humanoids.catalog import SPECS, robots  # noqa: E402
from gen.humanoids.model_parser import (  # noqa: E402
    MAX_PLAUSIBLE_JOINT_TORQUE_NM,
    parse_mjcf,
    parse_urdf,
)
from gen.humanoids.scaling_laws import (  # noqa: E402
    GENERALISES_OOS_R2,
    check_aethon,
    check_knee,
    dataset,
    fit_knee_law,
    fit_mass_height_law,
)
from gen.humanoids.validation import validate_robot  # noqa: E402
from gen.kinematics import knee_squat_hold_torque  # noqa: E402

# ── parser: torque-limit + joint-range extraction across the three conventions ────────────────────

_URDF_EFFORT = textwrap.dedent("""\
    <robot name="legbot">
      <link name="base"><inertial><mass value="10"/>
        <inertia ixx="1" ixy="0" ixz="0" iyy="1" iyz="0" izz="1"/></inertial></link>
      <link name="thigh"><inertial><mass value="2"/>
        <inertia ixx="0.1" ixy="0" ixz="0" iyy="0.1" iyz="0" izz="0.1"/></inertial></link>
      <link name="shank"><inertial><mass value="1"/>
        <inertia ixx="0.05" ixy="0" ixz="0" iyy="0.05" iyz="0" izz="0.05"/></inertial></link>
      <joint name="hip" type="revolute"><parent link="base"/><child link="thigh"/>
        <limit effort="120" lower="-1.57" upper="1.57" velocity="10"/></joint>
      <joint name="knee" type="revolute"><parent link="thigh"/><child link="shank"/>
        <limit effort="0" lower="0" upper="2.0" velocity="10"/></joint>
    </robot>
""")

_MJCF_MOTOR_GEAR = textwrap.dedent("""\
    <mujoco model="geared">
      <worldbody>
        <body name="trunk"><freejoint/>
          <inertial pos="0 0 0" mass="5" diaginertia="0.1 0.1 0.1"/>
          <body name="thigh">
            <joint name="knee" type="hinge" range="-0.2 2.0"/>
            <inertial pos="0 0 -0.2" mass="1" diaginertia="0.02 0.02 0.005"/>
            <body name="spring_link">
              <joint name="ankle_spring" type="hinge"/>
              <inertial pos="0 0 -0.1" mass="0.2" diaginertia="0.001 0.001 0.001"/>
            </body>
          </body>
        </body>
      </worldbody>
      <actuator>
        <motor name="knee" joint="knee" gear="16" ctrlrange="-12.2 12.2"/>
      </actuator>
    </mujoco>
""")

_MJCF_SENTINEL = textwrap.dedent("""\
    <mujoco model="sentinel">
      <worldbody>
        <body name="trunk"><freejoint/>
          <inertial pos="0 0 0" mass="5" diaginertia="0.1 0.1 0.1"/>
          <body name="thigh">
            <joint name="knee" type="hinge" actuatorfrcrange="-50000 50000"/>
            <inertial pos="0 0 -0.2" mass="1" diaginertia="0.02 0.02 0.005"/>
          </body>
        </body>
      </worldbody>
    </mujoco>
""")


def test_urdf_parses_effort_as_torque_and_zero_effort_is_an_honest_gap(tmp_path):
    p = tmp_path / "leg.urdf"
    p.write_text(_URDF_EFFORT)
    s = parse_urdf(p)
    hip = next(j for j in s.joints if j.name == "hip")
    knee = next(j for j in s.joints if j.name == "knee")
    assert hip.torque_limit_nm == pytest.approx(120.0)     # <limit effort=120>
    assert hip.range_span == pytest.approx(3.14)           # -1.57..1.57
    assert knee.torque_limit_nm is None                    # effort=0 ⇒ unspecified, NOT a 0 N·m cap
    assert s.max_joint_torque_nm == pytest.approx(120.0)
    assert s.torque_limit_for("hip") == pytest.approx(120.0)


def test_mjcf_motor_torque_is_ctrlrange_times_gear_not_ctrlrange_alone(tmp_path):
    """The Cassie subtlety: a <motor> output torque is |ctrlrange|·gear (16·12.2 = 195.2 N·m), not the
    bare ctrlrange. Mishandling this understates the joint torque 16×."""
    p = tmp_path / "geared.xml"
    p.write_text(_MJCF_MOTOR_GEAR)
    s = parse_mjcf(p)
    knee = next(j for j in s.joints if j.name == "knee")
    assert knee.torque_limit_nm == pytest.approx(16.0 * 12.2)   # 195.2, the JOINT torque
    assert knee.range_span == pytest.approx(2.2)


def test_mjcf_passive_spring_joint_is_not_counted_as_motorised(tmp_path):
    """A hinge with no actuator (a spring/linkage joint) is actuated-in-the-tree but NOT motorised —
    the distinction that makes Cassie's DOF count honest (20 tree hinges, 10 motorised)."""
    p = tmp_path / "geared.xml"
    p.write_text(_MJCF_MOTOR_GEAR)
    s = parse_mjcf(p)
    assert s.actuated_dof == 2                # both hinges are in the tree
    assert s.motorised_dof == 1               # only the knee has a <motor>; the spring is passive
    spring = next(j for j in s.joints if j.name == "ankle_spring")
    assert spring.actuated and not spring.motorised


def test_NEGATIVE_sentinel_torque_is_gated_to_none_not_taken_as_a_fact(tmp_path):
    """NEGATIVE TEST: a placeholder sentinel effort/forcerange (iCub uses 50000, ergoCub 1e9) is NOT a
    physical rating; the parser must report it as an honest None, never as a 50000 N·m 'fact'. A
    fabricated 5×10⁴ N·m knee would poison every scaling law — the no-hallucination contract forbids it."""
    p = tmp_path / "sentinel.xml"
    p.write_text(_MJCF_SENTINEL)
    s = parse_mjcf(p)
    knee = next(j for j in s.joints if j.name == "knee")
    assert 50000.0 >= MAX_PLAUSIBLE_JOINT_TORQUE_NM      # the value IS above the plausibility ceiling
    assert knee.torque_limit_nm is None                  # …so it is gated to an honest gap
    assert s.max_joint_torque_nm is None
    assert s.joint_torque_limits == ()


def test_real_ergocub_sentinel_is_an_honest_torque_gap_in_the_catalog():
    """End-to-end on the real ergoCub URDF: every joint ships effort=1e9; the catalog must carry NO
    fabricated torque (peak_joint_torque is an honest None with a sourced 'sentinel' reason)."""
    s = SPECS["ergocub"]
    assert s.peak_joint_torque_nm is not None        # the field exists…
    assert s.peak_joint_torque_nm.value is None      # …but the value is an honest gap
    assert "sentinel" in s.peak_joint_torque_nm.source.lower()


# ── the knee squat-hold closed form (the calibration fix's physics) ────────────────────────────────

def test_knee_squat_hold_is_zero_standing_and_max_at_horizontal_thigh():
    standing = knee_squat_hold_torque(body_mass=50.0, thigh_length=0.4, thigh_angle_from_vertical=0.0)
    deep = knee_squat_hold_torque(body_mass=50.0, thigh_length=0.4, thigh_angle_from_vertical=math.pi / 2)
    assert standing["knee_torque"] == pytest.approx(0.0)            # straight leg → no gravity torque
    # thigh horizontal: τ = 0.8·50·g·0.4 (supported_fraction default 0.8)
    assert deep["knee_torque"] == pytest.approx(0.8 * 50.0 * 9.80665 * 0.4)


def test_knee_squat_hold_rejects_nonsense():
    with pytest.raises(ValueError):
        knee_squat_hold_torque(body_mass=-1.0, thigh_length=0.4, thigh_angle_from_vertical=0.5)
    with pytest.raises(ValueError):
        knee_squat_hold_torque(body_mass=50.0, thigh_length=0.4, thigh_angle_from_vertical=2.0)  # >π/2


# ── the CALIBRATION FIX: shipping robots are no longer flagged as unable to hold their weight ──────

@pytest.mark.parametrize("key", ["apptronik_apollo", "pal_talos", "h1_2", "unitree_h1", "unitree_g1"])
def test_shipping_robot_knee_passes_the_squat_gate_after_calibration(key):
    """The core calibration finding: pre-fix, GENESIS's whole-leg-horizontal sizing over-predicted the
    knee demand ~2× and flagged these REAL, shipping robots as failing (capability < demand). The fixed
    squat-hold sizing must let each clear its own knee rating — a known-good robot passes the gate."""
    results = validate_robot(key)
    knee = [r for r in results if "knee squat-hold torque" in r.axis]
    assert knee, f"{key} should have a knee squat-hold axis"
    assert knee[0].verdict == "agree", f"{key} knee should meet the 60° squat reference, got {knee[0].verdict}"


def test_cassie_dof_agrees_after_excluding_passive_springs():
    """Cassie's tree has 20 hinges but 10 are passive springs; the DOF cross-check must compare the
    10 MOTORISED joints to the published 10 — agreeing — not the 20 tree hinges."""
    results = validate_robot("agility_cassie")
    dof = [r for r in results if r.axis.startswith("DOF")]
    assert dof and dof[0].verdict == "agree"
    assert "10 motorised joints" in dof[0].genesis_value
    assert "passive spring/linkage" in dof[0].genesis_value


# ── the discovered scaling laws + the keep-only-what-generalises discipline ───────────────────────

def test_dataset_is_assembled_from_real_catalog_facts_only():
    pts = dataset()
    assert len(pts) >= 15                       # plenty of robots have mass+height
    # every point's mgL is consistent with m·g·leg (no fabricated coordinate)
    for p in pts[:5]:
        assert p.mgL == pytest.approx(p.mass_kg * 9.80665 * p.leg_length_m)


def test_knee_law_generalises_out_of_sample_and_is_kept():
    law = fit_knee_law()
    assert law.name == "knee_torque_vs_mgL"
    assert 0.3 < law.coefficient < 0.8          # knee holds ~half the m·g·leg gravitational torque
    assert law.oos_r2 >= GENERALISES_OOS_R2      # validates leave-one-out → kept
    assert law.generalises
    assert 0.0 < law.band_lo < 1.0 < law.band_hi  # a real, positive-bounded fleet band


def test_mass_height_law_is_honestly_rejected_not_oversold():
    """The discovery discipline's other half: a law that does NOT generalise must be reported as
    rejected, never stored as validated. Height alone underdetermines mass → LOO R² below the bar."""
    law = fit_mass_height_law()
    assert law.oos_r2 < GENERALISES_OOS_R2
    assert not law.generalises
    assert "REJECTED" in law.note


def test_aethon_knee_sits_inside_the_real_fleet_band():
    """Our own design, checked against the law fitted from real robots: AETHON's knee must sit inside
    the real-fleet band — evidence the design is sane by the same standard the real fleet sets."""
    ac = check_aethon()
    assert ac.within_band, f"AETHON knee ratio {ac.ratio:.2f}× is outside the fleet band"
    assert ac.verdict == "in_band"
    assert 1.0 < ac.ratio < 2.0                 # carries sensible margin over the central law


def test_check_knee_flags_an_underactuated_design_low():
    """A clearly under-actuated knee (a 100 kg robot with a 10 N·m knee) must be flagged 'low' — the
    prior earns its keep by catching a bad design, not by rubber-stamping everything."""
    dc = check_knee(mass_kg=100.0, height_m=1.7, knee_torque_nm=10.0)
    assert dc.verdict == "low" and not dc.within_band


def test_check_knee_rejects_nonpositive():
    with pytest.raises(ValueError):
        check_knee(mass_kg=0.0, height_m=1.7, knee_torque_nm=100.0)
