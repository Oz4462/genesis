"""Tests for the CSG -> OpenSCAD exporter — deterministic, offline, no LLM.

The exporter turns a GATE-γ-validated GeometryNode tree into OpenSCAD source,
resolving every parameter quantity_id to its concrete value and annotating it
with the originating id (traceability). These tests pin the exact output and the
loud-failure behavior (unknown kind / missing param / absent quantity / no
geometry all raise ExportError, never a guessed number).

OpenSCAD syntax target (from the OpenSCAD language manual): cube([x,y,z]);
cylinder(h=H, r=R); sphere(r=R); difference(){...}; translate([x,y,z]){...}.

Run:  pytest tests/test_openscad.py
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
from gen.export.openscad import component_to_openscad, specification_to_openscad  # noqa: E402


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


# --- the happy path: exact output ---------------------------------------------

def test_bracket_exports_expected_openscad():
    comp = Component(id="c_bracket", name="bracket", geometry=_bracket_geometry())
    out = component_to_openscad(comp, _bracket_quantities())
    expected = (
        "module c_bracket() {\n"
        "  difference() {\n"
        "    cube([60, 80, 6], center=true); // size_x=q_w, size_y=q_h, size_z=q_t\n"
        "    cylinder(h=6, r=2.25, center=true); // height=q_t, radius=q_hole_r\n"
        "  }\n"
        "}\n"
        "c_bracket();"
    )
    assert out == expected


def test_sphere_and_translate_render():
    quantities = {q.id: q for q in (_q("r", 3.0), _q("dx", 1.0), _q("dy", 2.0), _q("dz", 3.0))}
    geom = GeometryNode(
        kind="translate",
        params={"x": "dx", "y": "dy", "z": "dz"},
        children=[GeometryNode(kind="sphere", params={"radius": "r"})],
    )
    comp = Component(id="ball", name="ball", geometry=geom)
    out = component_to_openscad(comp, quantities)
    assert "translate([1, 2, 3]) { // x=dx, y=dy, z=dz" in out
    assert "sphere(r=3); // radius=r" in out


def test_integral_and_fractional_values_render_cleanly():
    quantities = {q.id: q for q in (_q("a", 60.0), _q("b", 4.5), _q("c", 2.25))}
    geom = GeometryNode(kind="box", params={"size_x": "a", "size_y": "b", "size_z": "c"})
    out = component_to_openscad(Component(id="x", name="x", geometry=geom), quantities)
    assert "cube([60, 4.5, 2.25], center=true);" in out   # 60 not 60.0


# --- loud failure (never a guessed number) ------------------------------------

def test_missing_param_raises():
    geom = GeometryNode(kind="box", params={"size_x": "q_w", "size_y": "q_h"})  # size_z missing
    with pytest.raises(ExportError):
        component_to_openscad(Component(id="x", name="x", geometry=geom), _bracket_quantities())


def test_param_referencing_absent_quantity_raises():
    geom = GeometryNode(kind="sphere", params={"radius": "q_ghost"})
    with pytest.raises(ExportError):
        component_to_openscad(Component(id="x", name="x", geometry=geom), _bracket_quantities())


def test_unknown_kind_raises():
    geom = GeometryNode(kind="torus", params={})
    with pytest.raises(ExportError):
        component_to_openscad(Component(id="x", name="x", geometry=geom), _bracket_quantities())


def test_component_without_geometry_raises():
    with pytest.raises(ExportError):
        component_to_openscad(Component(id="x", name="x", geometry=None), {})


# --- whole-spec export --------------------------------------------------------

def test_specification_export_has_header_and_skips_non_geometry():
    spec = Specification(
        run_id="r1", idea="a bracket",
        quantities=list(_bracket_quantities().values()),
        components=[
            Component(id="c_bracket", name="bracket", geometry=_bracket_geometry()),
            Component(id="c_screw", name="screw", geometry=None),  # purchased
        ],
    )
    out = specification_to_openscad(spec)
    assert out.startswith("// GENESIS — Phase γ CSG export (OpenSCAD)")
    assert "// idea: a bracket" in out
    assert "module c_bracket()" in out
    assert "c_screw" in out and "no geometry — skipped" in out


def test_empty_geometry_spec_is_explicit():
    spec = Specification(run_id="r1", idea="nothing", components=[])
    out = specification_to_openscad(spec)
    assert "no fabricated geometry" in out
