"""urdf_bridge — the opt-in handoff from GENESIS's deterministic screens to a full dynamic simulator.

GENESIS's dynamics axis (dynamics.py) is a closed-form SCREEN: it answers "is this cadence / limb
dynamically feasible at first order" deterministically and offline. It deliberately does NOT run a
multibody contact simulation or learn a gait — that is what the world's humanoid stacks do in MuJoCo
and NVIDIA Isaac Lab (RL whole-body control, sim2real). This module is the bridge: it exports the
leg's links, revolute joints and inertials as a standard URDF — the exact format MuJoCo
(``mujoco`` URDF import), Isaac Lab and PyBullet load — so a GENESIS-verified design hands off to a
real dynamic simulator for gait optimisation and sim2real, WITHOUT GENESIS taking on an un-gated
simulation dependency. It is the handoff artifact, not a claim that GENESIS simulated the motion.

Deterministic, offline, standard-library only (``xml.etree``). Honest boundary: the inertia is a
diagonal placeholder built from the swing inertia; collision meshes, actuator/transmission models,
joint limits and contact/friction parameters are the simulator's (or the user's) to refine — this
emits the rigid-body tree and the inertials, the part a kinematic/inertial spec actually determines.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """One leg segment: a link of `length` [m] (with collision/visual `radius` [m]) and `mass` [kg]
    and a diagonal swing `inertia` [kg·m²] about its proximal joint, driven by a revolute joint
    named `joint`."""

    name: str
    joint: str
    length: float
    mass: float
    inertia: float
    radius: float = 0.03


def _inertial(parent: ET.Element, mass: float, inertia: float, com_z: float) -> None:
    el = ET.SubElement(parent, "inertial")
    ET.SubElement(el, "origin", {"xyz": f"0 0 {com_z:g}", "rpy": "0 0 0"})
    ET.SubElement(el, "mass", {"value": f"{mass:g}"})
    # diagonal placeholder inertia tensor (off-diagonal terms zero) — the simulator/user refines it
    ET.SubElement(el, "inertia", {
        "ixx": f"{inertia:g}", "iyy": f"{inertia:g}", "izz": f"{inertia:g}",
        "ixy": "0", "ixz": "0", "iyz": "0",
    })


def _shape(parent: ET.Element, tag: str, length: float, radius: float, com_z: float) -> None:
    """A cylinder ``collision`` or ``visual`` of `length` along the link's −z axis (centered at
    `com_z`), so a physics engine has a body to contact — without it the leg falls through the floor."""
    el = ET.SubElement(parent, tag)
    ET.SubElement(el, "origin", {"xyz": f"0 0 {com_z:g}", "rpy": "0 0 0"})
    geom = ET.SubElement(el, "geometry")
    ET.SubElement(geom, "cylinder", {"length": f"{length:g}", "radius": f"{radius:g}"})


def leg_urdf(
    name: str,
    segments: list[Segment],
    *,
    axis: tuple[float, float, float] = (0.0, 1.0, 0.0),
    effort: float = 100.0,
    velocity: float = 10.0,
    limit_rad: float = 1.5708,
) -> str:
    """Emit a minimal but valid URDF for a serial leg: a base link, then one revolute joint + link
    per ``Segment`` (each link hanging −z by its length, its CoM at mid-length, with the segment's
    mass and diagonal inertia). ``axis`` is the shared revolute axis (default the y pitch axis);
    ``effort``/``velocity``/``limit_rad`` set placeholder joint limits. Returns the URDF XML string,
    deterministically. Raises ValueError on an empty segment list or a non-positive length/mass."""
    if not segments:
        raise ValueError("need at least one segment")
    for s in segments:
        if s.length <= 0.0 or s.mass <= 0.0 or s.inertia <= 0.0:
            raise ValueError(f"segment {s.name!r}: length, mass and inertia must be positive")

    robot = ET.Element("robot", {"name": name})
    ET.SubElement(robot, "link", {"name": "base_link"})

    parent_link = "base_link"
    parent_length = 0.0
    axis_str = f"{axis[0]:g} {axis[1]:g} {axis[2]:g}"
    for seg in segments:
        joint = ET.SubElement(robot, "joint", {"name": seg.joint, "type": "revolute"})
        ET.SubElement(joint, "parent", {"link": parent_link})
        ET.SubElement(joint, "child", {"link": seg.name})
        # the joint sits at the distal end of the parent segment (the base sits at the origin)
        ET.SubElement(joint, "origin", {"xyz": f"0 0 {-parent_length:g}", "rpy": "0 0 0"})
        ET.SubElement(joint, "axis", {"xyz": axis_str})
        ET.SubElement(joint, "limit", {
            "lower": f"{-limit_rad:g}", "upper": f"{limit_rad:g}",
            "effort": f"{effort:g}", "velocity": f"{velocity:g}",
        })
        link = ET.SubElement(robot, "link", {"name": seg.name})
        _inertial(link, seg.mass, seg.inertia, com_z=-seg.length / 2.0)
        _shape(link, "collision", seg.length, seg.radius, com_z=-seg.length / 2.0)
        _shape(link, "visual", seg.length, seg.radius, com_z=-seg.length / 2.0)
        parent_link = seg.name
        parent_length = seg.length

    return ET.tostring(robot, encoding="unicode")


def _branch(robot: ET.Element, *, joint: str, parent: str, child: str,
            origin: tuple[float, float, float], length: float, mass: float, radius: float,
            axis: tuple[float, float, float] = (0.0, 1.0, 0.0), extend: float = -1.0) -> None:
    """Add one revolute joint (``parent`` → ``child`` at ``origin``) and its cylinder link, extending
    ``extend``·``length`` along z (−1 = downward limbs, +1 = upward torso/head). The URDF inertial
    tensor is about the COM, so a uniform rod is m·L²/12 (NOT m·L²/3, which is about the end)."""
    com_z = extend * length / 2.0
    j = ET.SubElement(robot, "joint", {"name": joint, "type": "revolute"})
    ET.SubElement(j, "parent", {"link": parent})
    ET.SubElement(j, "child", {"link": child})
    ET.SubElement(j, "origin", {"xyz": f"{origin[0]:g} {origin[1]:g} {origin[2]:g}", "rpy": "0 0 0"})
    ET.SubElement(j, "axis", {"xyz": f"{axis[0]:g} {axis[1]:g} {axis[2]:g}"})
    ET.SubElement(j, "limit", {"lower": "-2", "upper": "2", "effort": "150", "velocity": "12"})
    link = ET.SubElement(robot, "link", {"name": child})
    # uniform-rod inertia ABOUT THE COM (m·L²/12) — the URDF tensor is COM-referenced and the
    # simulator re-applies the parallel-axis shift m·(L/2)² from the joint, recovering m·L²/3 about
    # the joint (the value the dynamics SCREEN uses). Writing m·L²/3 here would double-count that shift.
    _inertial(link, mass, mass * length * length / 12.0, com_z=com_z)
    _shape(link, "collision", length, radius, com_z=com_z)
    _shape(link, "visual", length, radius, com_z=com_z)


def humanoid_urdf(
    name: str = "humanoid",
    *,
    thigh: tuple[float, float] = (0.40, 2.0),
    shank: tuple[float, float] = (0.40, 1.5),
    upper_arm: tuple[float, float] = (0.28, 1.2),
    forearm: tuple[float, float] = (0.25, 0.9),
    torso: tuple[float, float] = (0.35, 8.0),
    head: tuple[float, float] = (0.14, 3.0),
    pelvis_width: float = 0.22,
) -> str:
    """A full branched HUMANOID tree (not just a leg): a pelvis root that branches to TWO legs
    (hip→thigh→knee→shank) and an upward torso (spine) that branches to TWO arms
    (shoulder→upper_arm→elbow→forearm) and a head (neck). Left/right symmetric, every joint a y-axis
    (sagittal) revolute. Each ``(length_m, mass_kg)`` segment gets a cylinder collision/visual and a
    uniform-rod inertia. Returns a URDF loadable by PyBullet / Isaac / MuJoCo — the whole body, the
    handoff for a whole-body controller. Raises ValueError on a non-positive dimension/mass."""
    for label, (ln, ms) in (("thigh", thigh), ("shank", shank), ("upper_arm", upper_arm),
                            ("forearm", forearm), ("torso", torso), ("head", head)):
        if ln <= 0.0 or ms <= 0.0:
            raise ValueError(f"{label}: length and mass must be positive")
    if pelvis_width <= 0.0:
        raise ValueError("pelvis_width must be positive")

    robot = ET.Element("robot", {"name": name})
    pelvis = ET.SubElement(robot, "link", {"name": "pelvis"})
    _inertial(pelvis, 4.0, 4.0 * 0.12 * 0.12 / 12.0 * 2.0, com_z=0.0)
    _shape(pelvis, "collision", 0.12, pelvis_width / 2.0, com_z=0.0)
    _shape(pelvis, "visual", 0.12, pelvis_width / 2.0, com_z=0.0)

    tl, tm = torso
    hl, hm = head
    ual, uam = upper_arm
    fal, fam = forearm
    thl, thm = thigh
    shl, shm = shank
    half = pelvis_width / 2.0

    # spine: pelvis -> torso (upward), then neck: torso -> head (upward)
    _branch(robot, joint="spine", parent="pelvis", child="torso",
            origin=(0.0, 0.0, 0.06), length=tl, mass=tm, radius=pelvis_width / 2.2, extend=1.0)
    _branch(robot, joint="neck", parent="torso", child="head",
            origin=(0.0, 0.0, tl), length=hl, mass=hm, radius=hl / 2.0, extend=1.0)

    # arms: shoulder (near torso top) -> upper_arm (down) -> elbow -> forearm (down), both sides
    for side, sign in (("l", 1.0), ("r", -1.0)):
        _branch(robot, joint=f"{side}_shoulder", parent="torso", child=f"{side}_upper_arm",
                origin=(0.0, sign * half, tl * 0.92), length=ual, mass=uam, radius=0.035, extend=-1.0)
        _branch(robot, joint=f"{side}_elbow", parent=f"{side}_upper_arm", child=f"{side}_forearm",
                origin=(0.0, 0.0, -ual), length=fal, mass=fam, radius=0.03, extend=-1.0)

    # legs: hip (pelvis bottom) -> thigh (down) -> knee -> shank (down), both sides
    for side, sign in (("l", 1.0), ("r", -1.0)):
        _branch(robot, joint=f"{side}_hip", parent="pelvis", child=f"{side}_thigh",
                origin=(0.0, sign * half / 2.0, -0.06), length=thl, mass=thm, radius=0.045, extend=-1.0)
        _branch(robot, joint=f"{side}_knee", parent=f"{side}_thigh", child=f"{side}_shank",
                origin=(0.0, 0.0, -thl), length=shl, mass=shm, radius=0.04, extend=-1.0)

    return ET.tostring(robot, encoding="unicode")
