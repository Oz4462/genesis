"""The opt-in bridge to a real dynamic simulator: leg_urdf emits a valid URDF (the format MuJoCo /
Isaac Lab / PyBullet load) with one revolute joint + inertial link per leg segment. GENESIS hands its
verified rigid-body tree off for full gait simulation; it does not simulate the motion itself.

Offline, stdlib only. Run:  pytest tests/test_urdf_bridge.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.urdf_bridge import Segment, humanoid_urdf, leg_urdf  # noqa: E402


def _leg() -> str:
    return leg_urdf("humanoid_leg", [
        Segment("thigh", "hip", length=0.4, mass=2.0, inertia=0.1),
        Segment("shank", "knee", length=0.4, mass=1.5, inertia=0.08),
    ])


def test_leg_urdf_is_wellformed_with_revolute_joints_and_inertials():
    """A 2-segment leg emits a parseable URDF: base + thigh + shank links, hip + knee revolute joints,
    each link carrying the segment's mass — the rigid-body tree a simulator needs."""
    root = ET.fromstring(_leg())
    assert root.tag == "robot" and root.get("name") == "humanoid_leg"
    joints = root.findall("joint")
    assert [j.get("type") for j in joints] == ["revolute", "revolute"]
    assert [j.get("name") for j in joints] == ["hip", "knee"]
    assert {link.get("name") for link in root.findall("link")} == {"base_link", "thigh", "shank"}
    assert sorted(float(m.get("value")) for m in root.findall(".//mass")) == [1.5, 2.0]


def test_knee_joint_sits_at_the_distal_end_of_the_thigh():
    """The serial chain is geometrically correct: the knee joint origin is at the end of the thigh
    link (z = −0.4 m), so the simulator builds the leg at the right length."""
    root = ET.fromstring(_leg())
    knee = next(j for j in root.findall("joint") if j.get("name") == "knee")
    assert knee.find("origin").get("xyz") == "0 0 -0.4"


def test_empty_or_bad_segment_raises():
    with pytest.raises(ValueError):
        leg_urdf("x", [])
    with pytest.raises(ValueError):
        leg_urdf("x", [Segment("a", "j", -1.0, 1.0, 1.0)])


def test_humanoid_urdf_is_a_wellformed_branched_tree():
    """The WHOLE BODY: a pelvis root that branches to two legs AND an upward torso that branches to two
    arms and a head — a valid URDF tree (10 revolute joints, 11 links), not a serial chain."""
    root = ET.fromstring(humanoid_urdf())
    assert {j.get("name") for j in root.findall("joint")} == {
        "spine", "neck", "l_shoulder", "r_shoulder", "l_elbow", "r_elbow",
        "l_hip", "r_hip", "l_knee", "r_knee"}
    assert {link.get("name") for link in root.findall("link")} == {
        "pelvis", "torso", "head", "l_upper_arm", "r_upper_arm", "l_forearm", "r_forearm",
        "l_thigh", "r_thigh", "l_shank", "r_shank"}
    assert all(j.get("type") == "revolute" for j in root.findall("joint"))


def test_humanoid_link_inertia_is_uniform_rod_about_the_com():
    """Physics anchor (regression guard): the URDF inertial tensor is COM-referenced, so a uniform-rod
    link must carry m·L²/12 — NOT m·L²/3 (about the end). The thigh (L=0.40 m, m=2.0 kg) → 0.0266667.
    The simulator re-applies the parallel-axis shift m·(L/2)² to recover m·L²/3 about the joint, so
    writing /3 here would double-count the offset and over-state the swing inertia 4×."""
    root = ET.fromstring(humanoid_urdf())
    thigh = next(link for link in root.findall("link") if link.get("name") == "l_thigh")
    inertia_el = thigh.find("inertial/inertia")
    assert inertia_el is not None
    ixx = float(inertia_el.get("ixx", "nan"))
    # rel=1e-5 absorbs the URDF's %g 6-sig-fig formatting; still pins the /12-vs-/3 (4×) physics.
    assert ixx == pytest.approx(2.0 * 0.40 * 0.40 / 12.0, rel=1e-5)


def test_humanoid_urdf_rejects_bad_dimensions():
    with pytest.raises(ValueError):
        humanoid_urdf(thigh=(-0.4, 2.0))
