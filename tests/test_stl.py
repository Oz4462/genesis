"""Tests for the CSG -> ASCII STL exporter — deterministic, offline, honest.

Pins: a box exports exactly 12 axis-aligned triangles, a cylinder tessellates to
4·segments triangles, sphere vertices lie on the sphere, translate shifts every
vertex, the STL structure is valid, and a CSG boolean raises ExportError (never a
wrong mesh — GENESIS defers booleans to the real-kernel exporters).

Run:  pytest tests/test_stl.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import ExportError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Component,
    GeometryNode,
    Quantity,
    Specification,
    ValueOrigin,
)
from gen.export.stl import (  # noqa: E402
    component_to_stl,
    specification_to_stl,
)


def _q(qid: str, value: float) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="t")


def _qs(*pairs) -> dict[str, Quantity]:
    return {qid: _q(qid, v) for qid, v in pairs}


def _facet_count(stl: str) -> int:
    return stl.count("facet normal")


def _vertices(stl: str) -> list[tuple[float, float, float]]:
    out = []
    for line in stl.splitlines():
        line = line.strip()
        if line.startswith("vertex "):
            _, x, y, z = line.split()
            out.append((float(x), float(y), float(z)))
    return out


# --- box: exact 12 triangles, valid structure ---------------------------------

def test_box_has_twelve_triangles_and_valid_structure():
    geom = GeometryNode(kind="box", params={"size_x": "x", "size_y": "y", "size_z": "z"})
    stl = component_to_stl(Component(id="b", name="b", geometry=geom), _qs(("x", 2.0), ("y", 4.0), ("z", 6.0)))
    assert stl.startswith("solid b")
    assert stl.rstrip().endswith("endsolid b")
    assert _facet_count(stl) == 12
    # every box facet normal is an axis-aligned unit vector
    for line in stl.splitlines():
        if line.strip().startswith("facet normal"):
            _, _, nx, ny, nz = line.split()
            n = (float(nx), float(ny), float(nz))
            assert pytest.approx(sum(abs(c) for c in n), abs=1e-6) == 1.0
            assert sum(1 for c in n if abs(c) > 1e-9) == 1   # exactly one axis


def test_box_vertices_are_centered():
    geom = GeometryNode(kind="box", params={"size_x": "x", "size_y": "y", "size_z": "z"})
    stl = component_to_stl(Component(id="b", name="b", geometry=geom), _qs(("x", 2.0), ("y", 2.0), ("z", 2.0)))
    xs = {round(v[0], 6) for v in _vertices(stl)}
    assert xs == {-1.0, 1.0}        # centered ±1


# --- cylinder: 4·segments triangles -------------------------------------------

def test_cylinder_triangle_count():
    geom = GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"})
    stl = component_to_stl(Component(id="c", name="c", geometry=geom), _qs(("r", 5.0), ("h", 10.0)), segments=8)
    assert _facet_count(stl) == 32          # 2*8 side + 8 + 8 caps


# --- sphere: vertices lie on the sphere ---------------------------------------

def test_sphere_vertices_on_surface():
    geom = GeometryNode(kind="sphere", params={"radius": "r"})
    stl = component_to_stl(Component(id="s", name="s", geometry=geom), _qs(("r", 3.0)), segments=8, rings=6)
    for x, y, z in _vertices(stl):
        assert math.sqrt(x * x + y * y + z * z) == pytest.approx(3.0, abs=1e-6)
    assert _facet_count(stl) > 0


# --- translate shifts every vertex --------------------------------------------

def test_translate_shifts_mesh():
    geom = GeometryNode(
        kind="translate", params={"x": "dx", "y": "z0", "z": "z0"},
        children=[GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})],
    )
    stl = component_to_stl(Component(id="t", name="t", geometry=geom),
                           _qs(("s", 2.0), ("dx", 10.0), ("z0", 0.0)))
    xs = {round(v[0], 6) for v in _vertices(stl)}
    assert xs == {9.0, 11.0}        # centered ±1 then shifted +10


# --- honesty: CSG booleans are NOT mesh-evaluated -----------------------------

def test_boolean_raises_not_a_wrong_mesh():
    geom = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "x", "size_y": "x", "size_z": "x"}),
        GeometryNode(kind="cylinder", params={"radius": "r", "height": "x"}),
    ])
    with pytest.raises(ExportError):
        component_to_stl(Component(id="d", name="d", geometry=geom), _qs(("x", 10.0), ("r", 2.0)))


def test_spec_with_only_booleans_raises_with_pointer():
    geom = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "x", "size_y": "x", "size_z": "x"}),
        GeometryNode(kind="cylinder", params={"radius": "r", "height": "x"}),
    ])
    spec = Specification(run_id="r", idea="i", quantities=list(_qs(("x", 10.0), ("r", 2.0)).values()),
                         components=[Component(id="d", name="d", geometry=geom)])
    with pytest.raises(ExportError) as exc:
        specification_to_stl(spec)
    assert "scad" in str(exc.value) or "b123d" in str(exc.value)


def test_spec_emits_meshable_components():
    box = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})
    spec = Specification(run_id="r", idea="i", quantities=list(_qs(("s", 2.0)).values()),
                         components=[Component(id="plate", name="plate", geometry=box)])
    stl = specification_to_stl(spec)
    assert "solid plate" in stl and _facet_count(stl) == 12


# --- loud failure on bad geometry ---------------------------------------------

def test_unknown_kind_raises():
    with pytest.raises(ExportError):
        component_to_stl(Component(id="x", name="x", geometry=GeometryNode(kind="torus", params={})), {})
