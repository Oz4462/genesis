"""Tests for GATE δ — deterministic geometric validation, no LLM, no network.

Proves the δ guarantee (PHASE_DELTA.md §4/§5): δ flags only PROVABLY dead/empty
geometric operations (disjoint bounding boxes), never a false positive, and never
a physics judgement. A valid design passes; a hole that misses the part, an
intersection of non-touching parts, and degenerate geometry each fail.

Run:  pytest tests/test_gate_delta.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    Component,
    GeometryNode,
    Question,
    Quantity,
    RunState,
    Specification,
    ValueOrigin,
)
from gen.verification.gates import gate_delta, geometry_envelope  # noqa: E402


def _q(qid: str, value: float) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="t")


def _state(component: Component, quantities: list[Quantity]) -> RunState:
    st = RunState(question=Question(raw="i", run_id="r"))
    st.specification = Specification(
        run_id="r", idea="i", quantities=quantities, components=[component]
    )
    return st


def _codes(state: RunState) -> set[str]:
    return {f.code for f in gate_delta(state).failures}


def _box(sx, sy, sz):
    return GeometryNode(kind="box", params={"size_x": sx, "size_y": sy, "size_z": sz})


# --- valid design passes ------------------------------------------------------

def test_valid_bracket_passes():
    # box 60x80x6 with a centered through-hole (cylinder inside the body)
    q = [_q("w", 60.0), _q("h", 80.0), _q("t", 6.0), _q("r", 2.25)]
    geom = GeometryNode(kind="difference", children=[
        _box("w", "h", "t"),
        GeometryNode(kind="cylinder", params={"radius": "r", "height": "t"}),
    ])
    state = _state(Component(id="c", name="bracket", geometry=geom), q)
    result = gate_delta(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_component_without_geometry_passes_trivially():
    state = _state(Component(id="c", name="screw", geometry=None), [])
    assert gate_delta(state).passed


# --- D-3: dead difference (hole misses the part) ------------------------------

def test_hole_that_misses_the_part_is_dead():
    q = [_q("w", 60.0), _q("h", 80.0), _q("t", 6.0), _q("r", 2.0), _q("far", 500.0), _q("z0", 0.0)]
    geom = GeometryNode(kind="difference", children=[
        _box("w", "h", "t"),
        GeometryNode(kind="translate", params={"x": "far", "y": "z0", "z": "z0"},
                     children=[GeometryNode(kind="cylinder", params={"radius": "r", "height": "t"})]),
    ])
    state = _state(Component(id="c", name="bracket", geometry=geom), q)
    assert "DEAD_OPERATION" in _codes(state)


# --- D-2: empty intersection (non-touching parts) -----------------------------

def test_intersection_of_disjoint_parts_is_empty():
    q = [_q("s", 10.0), _q("far", 100.0), _q("z0", 0.0)]
    a = _box("s", "s", "s")
    b = GeometryNode(kind="translate", params={"x": "far", "y": "z0", "z": "z0"}, children=[a])
    geom = GeometryNode(kind="intersection", children=[a, b])
    state = _state(Component(id="c", name="part", geometry=geom), q)
    codes = _codes(state)
    assert "EMPTY_INTERSECTION" in codes or "EMPTY_GEOMETRY_TREE" in codes


# --- D-1: degenerate geometry -------------------------------------------------

def test_zero_axis_is_degenerate():
    q = [_q("w", 60.0), _q("h", 80.0), _q("t", 0.0)]   # zero thickness
    state = _state(Component(id="c", name="flat", geometry=_box("w", "h", "t")), q)
    assert "DEGENERATE_GEOMETRY" in _codes(state)


# --- D-0 ----------------------------------------------------------------------

def test_no_specification_fails():
    st = RunState(question=Question(raw="i", run_id="r"))
    st.specification = None
    assert "NO_SPECIFICATION" in _codes(st)


# --- honesty: δ makes no physics judgement (D-7) ------------------------------

def test_thin_wall_still_passes_delta_makes_no_strength_claim():
    # a paper-thin but geometrically valid bracket: δ must NOT flag it. δ judges
    # geometry, not strength — claiming "too thin to hold the load" would be a
    # fabricated physics verdict.
    q = [_q("w", 60.0), _q("h", 80.0), _q("t", 0.01), _q("r", 2.0)]
    geom = GeometryNode(kind="difference", children=[
        _box("w", "h", "t"),
        GeometryNode(kind="cylinder", params={"radius": "r", "height": "t"}),
    ])
    state = _state(Component(id="c", name="thin", geometry=geom), q)
    assert gate_delta(state).passed


# --- D-5: envelope surface ----------------------------------------------------

def test_envelope_reports_extent():
    q = [_q("w", 60.0), _q("h", 80.0), _q("t", 6.0)]
    state = _state(Component(id="c_bracket", name="bracket", geometry=_box("w", "h", "t")), q)
    env = geometry_envelope(state)
    assert env["c_bracket"] == (60.0, 80.0, 6.0)
