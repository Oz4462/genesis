"""Rotation in the CSG vocabulary — proven through EVERY layer, never asserted.

The anchors are exact: a 90°-z-rotated 10×20×30 box has AABB extents (20,10,30)
to machine precision; rotation preserves volume exactly (rigid motion); the AABB
of a 45°-rotated cylinder must CONTAIN the kernel-exact bounding box
(conservative, never too small); the OCCT solid of a 90°-x-rotated cylinder has
its axis along Y with the same exact volume; both script exporters emit the
documented backend APIs (OpenSCAD ``rotate(a, v)``; build123d
``Shape.rotate(Axis, deg)``); the primitive STL mesher's rotated mesh stays
watertight with the exact volume; and the print layer sees the physical truth —
a lying cylinder has LINE contact, no plate adhesion. A zero axis raises in
every layer; it is never guessed.

Offline, no LLM. Kernel cases are cadquery-gated.

Run:  pytest tests/test_rotate.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.core.state import Component, GeometryNode, Quantity, ValueOrigin  # noqa: E402
from gen.verification.geometry import aabb_of, rotate_point, volume_of  # noqa: E402


def _q(qid, v, unit="mm"):
    return Quantity(id=qid, name=qid, value=v, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="x")


QS = {q.id: q for q in [
    _q("sx", 10.0), _q("sy", 20.0), _q("sz", 30.0),
    _q("r", 5.0), _q("h", 20.0),
    _q("zero", 0.0), _q("one", 1.0),
    _q("a90", 90.0, "deg"), _q("a45", 45.0, "deg"),
]}

BOX = GeometryNode(kind="box", params={"size_x": "sx", "size_y": "sy", "size_z": "sz"})
CYL = GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"})


def _rot(child, ax, ay, az, angle):
    return GeometryNode(kind="rotate",
                        params={"axis_x": ax, "axis_y": ay, "axis_z": az,
                                "angle_deg": angle},
                        children=[child])


# ------------------------------------------------------------- Rodrigues core
def test_rotate_point_exact_quarter_turn():
    x, y, z = rotate_point((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), 90.0)
    assert abs(x) < 1e-12 and abs(y - 1.0) < 1e-12 and abs(z) < 1e-12


def test_rotate_point_zero_axis_raises():
    with pytest.raises(GeometryError):
        rotate_point((1.0, 0.0, 0.0), (0.0, 0.0, 0.0), 30.0)


# ------------------------------------------------------------------ AABB layer
def test_aabb_quarter_turn_is_exact():
    bb = aabb_of(_rot(BOX, "zero", "zero", "one", "a90"), QS)
    ex = bb.extent
    assert abs(ex[0] - 20.0) < 1e-9 and abs(ex[1] - 10.0) < 1e-9 and abs(ex[2] - 30.0) < 1e-9


def test_aabb_45deg_is_conservative_never_too_small():
    bb = aabb_of(_rot(BOX, "zero", "zero", "one", "a45"), QS)
    # the true rotated box needs (10+20)/sqrt(2) in x and y — the bound must
    # cover at least that (here it equals it: a box fills its own AABB)
    need = 30.0 / math.sqrt(2.0)
    assert bb.extent[0] >= need - 1e-9 and bb.extent[1] >= need - 1e-9
    assert abs(bb.extent[2] - 30.0) < 1e-9


def test_volume_is_rotation_invariant_and_stays_exact():
    v = volume_of(_rot(BOX, "zero", "zero", "one", "a45"), QS)
    assert v.exact and v.value == pytest.approx(10.0 * 20.0 * 30.0)


def test_aabb_and_volume_reject_zero_axis():
    bad = _rot(BOX, "zero", "zero", "zero", "a45")
    with pytest.raises(GeometryError):
        aabb_of(bad, QS)
    with pytest.raises(GeometryError):
        volume_of(bad, QS)


# ------------------------------------------------------------------ BREP layer
def test_brep_rotated_cylinder_lies_along_y_with_exact_volume():
    pytest.importorskip("cadquery", reason="exact BREP needs cadquery/OCP")
    from gen.brep import csg_to_solid, exact_volume

    lying = _rot(CYL, "one", "zero", "zero", "a90")        # z-axis -> y-axis
    vol = exact_volume(lying, QS)
    assert vol == pytest.approx(math.pi * 25.0 * 20.0, rel=1e-9)   # invariant
    bb = csg_to_solid(lying, QS).BoundingBox()
    assert abs((bb.xmax - bb.xmin) - 10.0) < 1e-6          # diameter
    assert abs((bb.ymax - bb.ymin) - 20.0) < 1e-6          # the height, now in y
    assert abs((bb.zmax - bb.zmin) - 10.0) < 1e-6          # diameter


def test_aabb_contains_the_kernel_exact_bbox():
    pytest.importorskip("cadquery", reason="exact BREP needs cadquery/OCP")
    from gen.brep import csg_to_solid

    tilted = _rot(CYL, "one", "zero", "zero", "a45")
    bb = aabb_of(tilted, QS)
    kb = csg_to_solid(tilted, QS).BoundingBox()
    eps = 1e-6
    assert bb.min_x <= kb.xmin + eps and bb.max_x >= kb.xmax - eps
    assert bb.min_y <= kb.ymin + eps and bb.max_y >= kb.ymax - eps
    assert bb.min_z <= kb.zmin + eps and bb.max_z >= kb.zmax - eps


# ------------------------------------------------------------------- exporters
def test_openscad_emits_the_documented_rotate_call():
    from gen.export.openscad import component_to_openscad

    comp = Component(id="c_rot", name="rotated box",
                     geometry=_rot(BOX, "zero", "zero", "one", "a45"))
    out = component_to_openscad(comp, QS)
    assert "rotate(a=45" in out and "v=[0, 0, 1]" in out
    assert "cube([10, 20, 30]" in out


def test_build123d_emits_the_documented_axis_rotate():
    from gen.export.build123d import component_to_build123d

    comp = Component(id="c_rot", name="rotated box",
                     geometry=_rot(BOX, "zero", "zero", "one", "a45"))
    out = component_to_build123d(comp, QS)
    assert ".rotate(Axis((0, 0, 0), (0, 0, 1)), 45)" in out


def test_primitive_stl_mesh_rotates_watertight_with_exact_volume():
    from gen.export.stl import component_to_stl
    from gen.mesh_integrity import stl_integrity_check

    comp = Component(id="c_rot", name="rotated box",
                     geometry=_rot(BOX, "one", "zero", "zero", "a45"))
    stl = component_to_stl(comp, QS)
    r = stl_integrity_check(stl)
    assert r["ok"], r["issues"]
    assert r["volume"] == pytest.approx(6000.0)            # rigid: 10*20*30


def test_stl_rejects_zero_axis():
    from gen.export.stl import component_to_stl

    comp = Component(id="c_bad", name="bad axis",
                     geometry=_rot(BOX, "zero", "zero", "zero", "a45"))
    with pytest.raises(GeometryError):
        component_to_stl(comp, QS)


# --------------------------------------------------- the print-layer payoff
def test_lying_cylinder_has_line_contact_no_adhesion():
    pytest.importorskip("cadquery", reason="orientation needs cadquery/OCP")
    from gen.orientation import first_layer_report

    lying = _rot(CYL, "one", "zero", "zero", "a90")
    r = first_layer_report(lying, QS)
    # the convergence probe (tolerance AND band refined 16x) exposes the contact
    # as a tessellation artifact: the band area shrinks ~4x -> vanishing -> no
    # adhesion. The working-mesh band area stays as honest evidence.
    assert r["vanishing_contact"] and not r["plate_contact"]
    assert r["contact_area"] > 0.0                         # evidence, not hidden
    assert r["contact_area_refined"] < 0.5 * r["contact_area"]
    assert not r["elephant_foot_risk"]                     # no contact, no bulge risk


def test_gate_delta_accepts_a_rotated_part():
    # the δ AABB gate walks the tree: a rotated part must validate cleanly
    from gen.core.state import Question, RunState, Specification
    from gen.verification.gates import gate_delta

    spec = Specification(
        run_id="rot", idea="rotated cylinder part", quantities=list(QS.values()),
        components=[Component(id="c1", name="lying cylinder",
                              geometry=_rot(CYL, "one", "zero", "zero", "a90"))],
    )
    st = RunState(question=Question(raw="x", run_id="rot"))
    st.specification = spec
    g = gate_delta(st)
    assert g.passed, [f.detail for f in g.failures]
