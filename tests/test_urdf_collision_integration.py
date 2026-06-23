"""Convex collision (CoACD) + urchin validation of emitted URDFs — real-tool integration.

urdf_bridge emits a rigid-body tree whose ``<collision>`` is a cylinder PRIMITIVE. This
suite pins the opt-in upgrade and validation that turn that handoff artifact into one a
contact simulator can use:

  * POSITIVE (collision): :func:`urdf_with_convex_collision` replaces each cylinder
    ``<collision>`` with a REAL CoACD convex decomposition (OBJ hulls referenced by the
    rewritten URDF), and the OBJs are written;
  * POSITIVE (validation): :func:`validate_urdf` loads the result with ``urchin``, runs
    forward kinematics (every link gets a world transform), AND loads the convex
    collision meshes — proving the emitted tree is kinematically valid AND its colliders
    actually load (end to end), not merely well-formed XML;
  * NEGATIVE (no-op refusal): a URDF with no cylinder collisions raises rather than write
    a silently-unchanged file;
  * NEGATIVE (validation): urchin rejects a structurally broken URDF (a joint whose
    parent link does not exist) — a broken handoff fails loud, it does not pass.

Two FAST unit tests (no heavy deps) always run: the availability probes return bools, and
a missing URDF path is a loud GeometryError. The CoACD/urchin tests SKIP when those
optional packages are absent (the ``_integration`` suffix marks them slow/dep-dependent).

Engines: trimesh + CoACD (decompose) + urchin (parse/FK). Deterministic (CoACD seed=0).
Run:  pytest tests/test_urdf_collision_integration.py
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.urdf_bridge import (  # noqa: E402
    Segment,
    coacd_available,
    humanoid_urdf,
    leg_urdf,
    urchin_available,
    urdf_with_convex_collision,
    validate_urdf,
)

_HAVE_COACD = coacd_available()
_HAVE_URCHIN = urchin_available()
_skip_no_coacd = pytest.mark.skipif(
    not _HAVE_COACD, reason="convex collision needs the optional coacd + trimesh packages")
_skip_no_urchin = pytest.mark.skipif(
    not _HAVE_URCHIN, reason="URDF validation needs the optional urchin package")


def _leg() -> str:
    return leg_urdf("test_leg", [
        Segment("thigh", "hip", length=0.4, mass=2.0, inertia=0.1),
        Segment("shank", "knee", length=0.4, mass=1.5, inertia=0.08),
    ])


# --- FAST unit tests (no heavy deps) -----------------------------------------------

def test_availability_probes_are_bools():
    assert isinstance(coacd_available(), bool)
    assert isinstance(urchin_available(), bool)


@_skip_no_urchin
def test_missing_urdf_path_is_loud(tmp_path):
    with pytest.raises(GeometryError):
        validate_urdf(tmp_path / "does_not_exist.urdf")


# --- POSITIVE / NEGATIVE integration tests -----------------------------------------

@_skip_no_coacd
def test_convex_collision_replaces_cylinders_with_meshes(tmp_path):
    out = urdf_with_convex_collision(_leg(), tmp_path)
    root = ET.parse(out).getroot()
    # every link's collision is now a <mesh>, never a <cylinder>
    for link in root.findall("link"):
        for coll in link.findall("collision"):
            assert coll.find("geometry/mesh") is not None
            assert coll.find("geometry/cylinder") is None
    # the convex-part OBJs were actually written
    objs = list((tmp_path / "collision").glob("*.obj"))
    assert len(objs) >= 2, objs


@_skip_no_coacd
def test_no_op_when_nothing_to_upgrade_is_loud(tmp_path):
    """A URDF with no cylinder collisions raises — refusing to write a silently-unchanged
    file (which would falsely look 'upgraded')."""
    plain = '<robot name="x"><link name="base_link"/></robot>'
    with pytest.raises(GeometryError):
        urdf_with_convex_collision(plain, tmp_path)


@_skip_no_urchin
def test_validate_primitive_urdf_with_fk(tmp_path):
    """The as-emitted (cylinder-primitive) leg URDF parses and FKs: 3 links, 2 actuated
    revolute joints, a world transform for every link."""
    p = tmp_path / "leg_prim.urdf"
    p.write_text(_leg())
    v = validate_urdf(p, load_collision_meshes=False)
    assert v.robot_name == "test_leg"
    assert v.n_links == 3 and v.n_joints == 2 and v.n_actuated_joints == 2
    assert v.fk_link_count == 3


@_skip_no_urchin
@_skip_no_coacd
def test_convex_urdf_validates_and_loads_collision_meshes(tmp_path):
    """End to end: upgrade the leg to convex collision, then urchin loads the URDF, FKs
    it, AND loads the collision meshes — the colliders are real and wired."""
    out = urdf_with_convex_collision(_leg(), tmp_path)
    v = validate_urdf(out, load_collision_meshes=True)
    assert v.n_links == 3
    assert v.collision_mesh_links >= 2  # both moving links have a loadable mesh collider


@_skip_no_urchin
@_skip_no_coacd
def test_whole_body_humanoid_convex_validates(tmp_path):
    """The whole-body humanoid (pelvis + 2 legs + spine + 2 arms + head) upgrades and
    validates: 11 links, 10 joints, and a collision mesh loaded for every link."""
    out = urdf_with_convex_collision(humanoid_urdf("hum"), tmp_path)
    v = validate_urdf(out, load_collision_meshes=True)
    assert v.n_links == 11 and v.n_joints == 10
    assert v.collision_mesh_links == 11


@_skip_no_urchin
def test_structurally_broken_urdf_is_rejected(tmp_path):
    """A joint whose parent link does not exist is not a valid robot — urchin rejects it
    and validate_urdf fails loud (a broken handoff never passes silently)."""
    broken = (
        '<robot name="b"><link name="a"/>'
        '<joint name="j" type="revolute">'
        '<parent link="GHOST"/><child link="a"/>'
        '<axis xyz="0 1 0"/>'
        '<limit lower="-1" upper="1" effort="1" velocity="1"/>'
        "</joint></robot>"
    )
    p = tmp_path / "broken.urdf"
    p.write_text(broken)
    with pytest.raises(GeometryError):
        validate_urdf(p, load_collision_meshes=False)
