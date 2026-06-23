"""urdf_bridge — the opt-in handoff from GENESIS's deterministic screens to a full dynamic simulator.

GENESIS's dynamics axis (dynamics.py) is a closed-form SCREEN: it answers "is this cadence / limb
dynamically feasible at first order" deterministically and offline. It deliberately does NOT run a
multibody contact simulation or learn a gait — that is what the world's humanoid stacks do in MuJoCo
and NVIDIA Isaac Lab (RL whole-body control, sim2real). This module is the bridge: it exports the
leg's links, revolute joints and inertials as a standard URDF — the exact format MuJoCo
(``mujoco`` URDF import), Isaac Lab and PyBullet load — so a GENESIS-verified design hands off to a
real dynamic simulator for gait optimisation and sim2real, WITHOUT GENESIS taking on an un-gated
simulation dependency. It is the handoff artifact, not a claim that GENESIS simulated the motion.

Deterministic, offline, standard-library only (``xml.etree``) for the EMITTERS. Honest boundary:
the inertia is a diagonal placeholder built from the swing inertia; actuator/transmission models,
joint limits and contact/friction parameters are the simulator's (or the user's) to refine — this
emits the rigid-body tree and the inertials, the part a kinematic/inertial spec actually determines.

Collision upgrade (opt-in, heavier deps lazy-imported so the emitters stay stdlib-only):
:func:`urdf_with_convex_collision` replaces the cylinder-PRIMITIVE ``<collision>`` blocks this module
emits with a REAL CoACD convex decomposition of each link (a watertight trimesh cylinder, decomposed
into convex hull pieces written as OBJ, referenced from the rewritten URDF) — the collision shape a
contact simulator can use robustly. :func:`validate_urdf` then PARSES the emitted URDF with ``urchin``
and runs forward kinematics (``link_fk``), proving the emitted tree is not just well-formed XML but a
kinematically valid robot whose links place where the geometry says (and, with convex collision, whose
collision meshes actually load). Both fail LOUD (no silent fallback to the broken/missing collision).
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .core.errors import GeometryError
from .mechanics_formulas import rod_inertia_about_center


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
    # uniform-rod inertia ABOUT THE COM — the URDF tensor is COM-referenced and the simulator
    # re-applies the parallel-axis shift m·(L/2)² from the joint, recovering m·L²/3 about the joint
    # (the value the dynamics SCREEN uses). The canonical, axis-named formula prevents the m·L²/3
    # (about-end) value from being written here by mistake.
    _inertial(link, mass, rod_inertia_about_center(mass, length), com_z=com_z)
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
    # stubby root link — diagonal placeholder inertia from the canonical rod formula (no inline magic
    # number); the simulator/user refines the true cuboid tensor.
    _inertial(pelvis, 4.0, rod_inertia_about_center(4.0, 0.12), com_z=0.0)
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


# --- Convex collision (CoACD) + urchin validation -----------------------------------
#
# The emitters above write a single cylinder PRIMITIVE as each link's <collision>. That
# is enough for a primitive collider, but for a real contact simulation the standard
# practice is a convex decomposition. These functions take a URDF this module EMITTED
# (cylinder links) and replace each <collision> with a CoACD convex decomposition of
# that cylinder, then validate the whole thing with urchin (parse + forward kinematics).
# Heavy deps (trimesh / coacd / urchin) are lazy-imported so importing this module — and
# the rest of GENESIS — never requires them; the emitters stay stdlib-only.


def coacd_available() -> bool:
    """True iff the ``coacd`` convex-decomposition package can be imported (optional)."""
    try:
        import coacd  # noqa: F401
        return True
    except Exception:
        return False


def urchin_available() -> bool:
    """True iff the ``urchin`` URDF parser/FK package can be imported (optional)."""
    try:
        import urchin  # noqa: F401
        return True
    except Exception:
        return False


def _cylinder_collisions(link: ET.Element) -> list[ET.Element]:
    """Every ``<collision>`` of ``link`` whose geometry is a ``<cylinder>`` (the shape
    the emitters write). Used to find what to convex-decompose."""
    out: list[ET.Element] = []
    for coll in link.findall("collision"):
        if coll.find("geometry/cylinder") is not None:
            out.append(coll)
    return out


def _decompose_cylinder(length: float, radius: float, *, max_convex_hull: int,
                        threshold: float, resolution: int):
    """Convex-decompose a watertight trimesh cylinder of ``length``×``radius`` (axis
    along z, centered at the origin) into a list of (vertices, faces) hulls. Deterministic
    (CoACD ``seed=0``). A cylinder is convex, so this typically yields one clean hull —
    the point is that the emitted collision becomes a real, simulator-robust convex mesh
    rather than a primitive the engine must special-case."""
    import coacd  # lazy
    import numpy as np
    import trimesh  # lazy

    mesh = trimesh.creation.cylinder(radius=radius, height=length, sections=24)
    if not mesh.is_watertight:
        raise GeometryError(
            f"cylinder mesh (l={length}, r={radius}) is not watertight — cannot make a "
            f"sound convex collider from it"
        )
    try:
        coacd.set_log_level("error")
    except Exception:
        pass
    cmesh = coacd.Mesh(mesh.vertices, mesh.faces)
    parts = coacd.run_coacd(
        cmesh, threshold=threshold, max_convex_hull=max_convex_hull,
        preprocess_mode="auto", preprocess_resolution=resolution, seed=0, merge=True,
    )
    hulls = []
    for v, f in parts:
        hull = trimesh.Trimesh(vertices=np.asarray(v), faces=np.asarray(f), process=True)
        if not hull.is_empty and len(hull.vertices) >= 4:
            hulls.append(hull)
    if not hulls:
        raise GeometryError(
            f"CoACD produced no usable convex parts for cylinder (l={length}, r={radius})"
        )
    return hulls


def urdf_with_convex_collision(
    urdf_xml: str,
    out_dir: str | Path,
    *,
    mesh_subdir: str = "collision",
    max_convex_hull: int = 4,
    threshold: float = 0.05,
    resolution: int = 50,
) -> str:
    """Rewrite a URDF this module emitted so each cylinder ``<collision>`` becomes a REAL
    CoACD convex-decomposed mesh collider.

    For every link, each cylinder ``<collision>`` is replaced by one ``<collision>`` per
    convex hull of that cylinder (same origin), the hulls written as OBJ under
    ``{out_dir}/{mesh_subdir}/`` and referenced by relative path. The ``<visual>`` blocks
    are left untouched, so the rendered robot is unchanged. The rewritten URDF is written
    to ``{out_dir}/<robot_name>.urdf`` and its path returned.

    This is the opt-in collision upgrade the module docstring describes: the emitted tree
    keeps its inertials and joints, but its collision geometry becomes the convex meshes a
    contact simulator (PyBullet / MuJoCo / Isaac) handles robustly, instead of primitives.

    Raises:
        GeometryError: CoACD/trimesh unavailable, no cylinder collisions found to upgrade
            (a silently-unchanged URDF would defeat the purpose), or a degenerate mesh.
    """
    if not coacd_available():
        raise GeometryError(
            "convex collision needs the optional 'coacd' package (and 'trimesh'); install "
            "them, or load the cylinder-primitive URDF as emitted."
        )
    out_dir = Path(out_dir)
    mesh_dir = out_dir / mesh_subdir
    mesh_dir.mkdir(parents=True, exist_ok=True)

    root = ET.fromstring(urdf_xml)
    robot_name = root.get("name", "robot")
    n_upgraded = 0
    for link in root.findall("link"):
        link_name = link.get("name", "link")
        for idx, coll in enumerate(_cylinder_collisions(link)):
            cyl = coll.find("geometry/cylinder")
            length = float(cyl.get("length"))
            radius = float(cyl.get("radius"))
            origin = coll.find("origin")
            hulls = _decompose_cylinder(
                length, radius, max_convex_hull=max_convex_hull,
                threshold=threshold, resolution=resolution,
            )
            link.remove(coll)
            for h, hull in enumerate(hulls):
                obj_path = mesh_dir / f"{link_name}_coll{idx}_part{h}.obj"
                hull.export(str(obj_path))
                new_coll = ET.SubElement(link, "collision")
                if origin is not None:
                    o = ET.SubElement(new_coll, "origin")
                    o.set("xyz", origin.get("xyz", "0 0 0"))
                    o.set("rpy", origin.get("rpy", "0 0 0"))
                geom = ET.SubElement(new_coll, "geometry")
                rel = os.path.relpath(obj_path, out_dir).replace("\\", "/")
                ET.SubElement(geom, "mesh", {"filename": rel})
            n_upgraded += 1

    if n_upgraded == 0:
        raise GeometryError(
            "no cylinder <collision> blocks found to convert — was this URDF emitted by "
            "leg_urdf/humanoid_urdf? (refusing to write a silently-unchanged URDF)"
        )
    out_path = out_dir / f"{robot_name}.urdf"
    ET.ElementTree(root).write(str(out_path))
    return str(out_path)


@dataclass(frozen=True)
class UrdfValidation:
    """Result of validating an emitted URDF with urchin (parse + forward kinematics)."""

    robot_name: str
    n_links: int
    n_joints: int
    n_actuated_joints: int
    #: link name -> its 4×4 world transform at the zero configuration (FK output)
    fk_link_count: int
    #: how many links had a loadable collision MESH (0 if all collisions are primitives)
    collision_mesh_links: int


def validate_urdf(urdf_path: str | Path, *, load_collision_meshes: bool = True) -> UrdfValidation:
    """Validate a URDF with ``urchin``: PARSE it and run forward kinematics.

    A URDF can be well-formed XML yet not a valid robot (dangling joint parent/child,
    inconsistent tree, unloadable mesh). urchin builds the kinematic tree and, via
    :meth:`link_fk`, computes every link's world transform at the zero configuration —
    so a successful call proves the emitted tree is kinematically consistent, not merely
    syntactically valid. If ``load_collision_meshes`` and the URDF uses mesh colliders,
    ``collision_trimesh_fk`` is also called, proving the convex-collision OBJs actually
    load (the upgrade from :func:`urdf_with_convex_collision` is real, end to end).

    Raises:
        GeometryError: urchin is unavailable, or it rejects the URDF / a referenced mesh
            (loud — a broken handoff artifact must fail, not pass silently).
    """
    if not urchin_available():
        raise GeometryError(
            "validating a URDF needs the optional 'urchin' package; install it with "
            "`pip install urchin`."
        )
    from urchin import URDF  # lazy

    urdf_path = Path(urdf_path)
    if not urdf_path.is_file():
        raise GeometryError(f"URDF file not found: {urdf_path}")
    try:
        robot = URDF.load(str(urdf_path), lazy_load_meshes=False)
    except Exception as exc:  # noqa: BLE001 - any parse/build failure surfaced loudly
        raise GeometryError(f"urchin rejected URDF {urdf_path.name}: {exc}") from exc

    try:
        fk = robot.link_fk()  # {Link: 4x4} at the zero configuration
    except Exception as exc:  # noqa: BLE001
        raise GeometryError(
            f"urchin forward kinematics failed for {urdf_path.name}: {exc}"
        ) from exc

    collision_mesh_links = 0
    if load_collision_meshes:
        try:
            cfk = robot.collision_trimesh_fk()  # {Trimesh: 4x4}; loads collision meshes
            collision_mesh_links = len(cfk)
        except Exception as exc:  # noqa: BLE001 - a referenced collision mesh failed to load
            raise GeometryError(
                f"urchin could not load the collision meshes of {urdf_path.name}: {exc}"
            ) from exc

    actuated = [j for j in robot.joints if j.joint_type != "fixed"]
    return UrdfValidation(
        robot_name=robot.name,
        n_links=len(robot.links),
        n_joints=len(robot.joints),
        n_actuated_joints=len(actuated),
        fk_link_count=len(fk),
        collision_mesh_links=collision_mesh_links,
    )
