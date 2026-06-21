"""Tests for the CSG -> build123d (algebra mode) exporter — deterministic, offline.

The exporter turns a GATE-γ-validated GeometryNode tree into build123d Python.
These tests pin the exact output (algebra-mode operators +/-/&, Pos(...) *) and
the loud-failure behavior (unknown kind / missing param / absent quantity / no
geometry all raise ExportError, never a guessed number).

build123d algebra-mode target (from the build123d docs): Box(l,w,h);
Cylinder(r,h); Sphere(r); A + B; A - B; A & B; Pos(x,y,z) * obj.

Run:  pytest tests/test_build123d.py
"""

from __future__ import annotations

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
from gen.export.build123d import (  # noqa: E402
    component_to_build123d,
    specification_to_build123d,
)


def _q(qid: str, value: float, unit: str = "mm") -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="test")


def _bracket_quantities() -> dict[str, Quantity]:
    return {q.id: q for q in (
        _q("q_w", 60.0), _q("q_h", 80.0), _q("q_t", 6.0), _q("q_hole_r", 2.25),
    )}


def _bracket_geometry() -> GeometryNode:
    return GeometryNode(
        kind="difference",
        children=[
            GeometryNode(kind="box", params={"size_x": "q_w", "size_y": "q_h", "size_z": "q_t"}),
            GeometryNode(kind="cylinder", params={"radius": "q_hole_r", "height": "q_t"}),
        ],
    )


def test_bracket_exports_expected_build123d():
    comp = Component(id="c_bracket", name="bracket", geometry=_bracket_geometry())
    out = component_to_build123d(comp, _bracket_quantities())
    expected = (
        "# c_bracket  dims: q_w=60, q_h=80, q_t=6, q_hole_r=2.25\n"
        "c_bracket = (Box(60, 80, 6) - Cylinder(2.25, 6))"
    )
    assert out == expected


def test_union_and_intersection_operators():
    quantities = {q.id: q for q in (_q("a", 1.0), _q("b", 2.0), _q("c", 3.0), _q("r", 4.0))}
    union = GeometryNode(kind="union", children=[
        GeometryNode(kind="box", params={"size_x": "a", "size_y": "b", "size_z": "c"}),
        GeometryNode(kind="sphere", params={"radius": "r"}),
    ])
    out = component_to_build123d(Component(id="u", name="u", geometry=union), quantities)
    assert "Box(1, 2, 3) + Sphere(4)" in out
    inter = GeometryNode(kind="intersection", children=union.children)
    out2 = component_to_build123d(Component(id="i", name="i", geometry=inter), quantities)
    assert "Box(1, 2, 3) & Sphere(4)" in out2


def test_translate_uses_pos_multiplication():
    quantities = {q.id: q for q in (_q("r", 3.0), _q("dx", 1.0), _q("dy", 2.0), _q("dz", 3.0))}
    geom = GeometryNode(
        kind="translate",
        params={"x": "dx", "y": "dy", "z": "dz"},
        children=[GeometryNode(kind="sphere", params={"radius": "r"})],
    )
    out = component_to_build123d(Component(id="ball", name="ball", geometry=geom), quantities)
    assert "Pos(1, 2, 3) * Sphere(3)" in out


def test_nested_operation_is_parenthesized():
    # difference(union(box, sphere), cylinder) -> (Box + Sphere) - Cylinder
    quantities = {q.id: q for q in (
        _q("a", 1.0), _q("b", 2.0), _q("c", 3.0), _q("r", 4.0), _q("h", 5.0),
    )}
    geom = GeometryNode(kind="difference", children=[
        GeometryNode(kind="union", children=[
            GeometryNode(kind="box", params={"size_x": "a", "size_y": "b", "size_z": "c"}),
            GeometryNode(kind="sphere", params={"radius": "r"}),
        ]),
        GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"}),
    ])
    out = component_to_build123d(Component(id="x", name="x", geometry=geom), quantities)
    assert "((Box(1, 2, 3) + Sphere(4)) - Cylinder(4, 5))" in out


# --- loud failure -------------------------------------------------------------

def test_missing_param_raises():
    geom = GeometryNode(kind="box", params={"size_x": "q_w", "size_y": "q_h"})
    with pytest.raises(ExportError):
        component_to_build123d(Component(id="x", name="x", geometry=geom), _bracket_quantities())


def test_absent_quantity_raises():
    geom = GeometryNode(kind="sphere", params={"radius": "q_ghost"})
    with pytest.raises(ExportError):
        component_to_build123d(Component(id="x", name="x", geometry=geom), _bracket_quantities())


def test_unknown_kind_raises():
    geom = GeometryNode(kind="torus", params={})
    with pytest.raises(ExportError):
        component_to_build123d(Component(id="x", name="x", geometry=geom), _bracket_quantities())


def test_no_geometry_raises():
    with pytest.raises(ExportError):
        component_to_build123d(Component(id="x", name="x", geometry=None), {})


# --- whole spec ---------------------------------------------------------------

def test_specification_export_has_import_and_header():
    spec = Specification(
        run_id="r1", idea="a bracket",
        quantities=list(_bracket_quantities().values()),
        components=[
            Component(id="c_bracket", name="bracket", geometry=_bracket_geometry()),
            Component(id="c_screw", name="screw", geometry=None),
        ],
    )
    out = specification_to_build123d(spec)
    assert "from build123d import *" in out
    assert out.startswith("# GENESIS — Phase γ CSG export (build123d, algebra mode)")
    assert "c_bracket = (Box(60, 80, 6) - Cylinder(2.25, 6))" in out
    assert "c_screw" in out and "no geometry — skipped" in out
