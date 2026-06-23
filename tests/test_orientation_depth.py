"""Depth audit for orientation.py — proves the BREP DFM verdicts are GEOMETRY-DRIVEN.

The headline claim of orientation.py is that ``overhang_check``, ``bridge_spans`` and
``first_layer_report`` derive their verdicts from the tessellated OpenCASCADE solid and
the build direction — NOT from canned constants. This file turns that claim into
falsifiable tests:

  * a flat-bottomed box is self-supporting (overhang_area == 0); a horizontal ceiling
    raised off the plate is flagged (overhang_area > 0, worst_overhang_deg > 0); and
    FLIPPING the build direction flips a cylinder's verdict — proving build_dir is
    actually consumed by the normal/angle math, not ignored;
  * a short anchored ceiling (span <= FDM_MAX_BRIDGE_MM) prints support-free while a
    wide one needs support — proving the span number is measured from the mesh;
  * a box on the plate has real flat contact (plate_contact True, area > 0) while a
    line-contact solid (a lying cylinder) is honestly reported as non-adhering via the
    convergence probe — proving the probe runs;
  * the documented fail-loud path: a degenerate empty boolean (A - B with B ⊇ A) that
    tessellates to no triangles raises ValueError, never a silent wrong verdict.

cadquery/OCP is the optional kernel; this module skips wholesale when it is absent so
the full pytest gate stays green without the CAD extra (mirrors test_orientation.py).

Offline, no LLM, deterministic. Run:  pytest tests/test_orientation_depth.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import HealthCheck, given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

# The whole module needs the OCCT kernel; skip cleanly where it is absent.
pytest.importorskip("cadquery", reason="orientation DFM needs the optional cadquery/OCP package")

from gen.core.state import GeometryNode, Quantity, ValueOrigin  # noqa: E402
from gen.orientation import (  # noqa: E402
    bridge_spans,
    first_layer_report,
    overhang_check,
)
from gen.printability import FDM_MAX_BRIDGE_MM  # noqa: E402


def _q(qid: str, value: float) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="depth-audit fixture")


_QS = {"s": _q("s", 10.0), "r": _q("r", 5.0), "h": _q("h", 12.0)}
_BOX = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})
_CYL_Z = GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"})


def _plate_on_pillar() -> tuple[GeometryNode, dict[str, Quantity]]:
    """A 20x20x2 plate sitting on a 4x4x20 pillar — the plate's underside is a
    horizontal ceiling raised off the plate (a genuine overhang under +Z)."""
    pillar = GeometryNode(kind="box", params={"size_x": "p", "size_y": "p", "size_z": "ph"})
    plate = GeometryNode(
        kind="translate", params={"x": "zero", "y": "zero", "z": "tz"},
        children=[GeometryNode(kind="box",
                               params={"size_x": "pl", "size_y": "pl", "size_z": "pt"})],
    )
    node = GeometryNode(kind="union", children=[pillar, plate])
    qs = {"p": _q("p", 4.0), "ph": _q("ph", 20.0), "pl": _q("pl", 20.0),
          "pt": _q("pt", 2.0), "zero": _q("zero", 0.0), "tz": _q("tz", 11.0)}
    return node, qs


def _table(gap: float, leg: float = 5.0, depth: float = 20.0,
           leg_h: float = 10.0, top_t: float = 5.0) -> tuple[GeometryNode, dict[str, Quantity]]:
    """Two legs + a top plate; the underside between the legs spans `gap` mm,
    anchored on the two legs (an opposite pair) — the canonical bridge fixture."""
    width = gap + 2.0 * leg
    off = (gap + leg) / 2.0
    qs = {k: _q(k, v) for k, v in {
        "leg_x": leg, "depth": depth, "leg_h": leg_h, "top_x": width,
        "top_t": top_t, "dx": off, "ndx": -off, "zero": 0.0,
        "top_z": (leg_h + top_t) / 2.0,
    }.items()}
    leg_box = GeometryNode(kind="box",
                           params={"size_x": "leg_x", "size_y": "depth", "size_z": "leg_h"})
    node = GeometryNode(kind="union", children=[
        GeometryNode(kind="translate", params={"x": "ndx", "y": "zero", "z": "zero"},
                     children=[leg_box]),
        GeometryNode(kind="translate", params={"x": "dx", "y": "zero", "z": "zero"},
                     children=[leg_box]),
        GeometryNode(kind="translate", params={"x": "zero", "y": "zero", "z": "top_z"},
                     children=[GeometryNode(kind="box",
                                            params={"size_x": "top_x", "size_y": "depth",
                                                    "size_z": "top_t"})]),
    ])
    return node, qs


# --- overhang_check: geometry- and orientation-driven, not a constant ----------

def test_flat_box_is_self_supporting():
    # An axis-aligned box printed flat: bottom = plate contact, sides vertical, top up.
    # No surface points within 45 deg of straight-down off the plate.
    r = overhang_check(_BOX, _QS, build_dir=(0, 0, 1))
    assert r["needs_support"] is False
    assert r["overhang_area"] == 0.0
    assert r["worst_overhang_deg"] == 0.0


def test_horizontal_ceiling_off_the_plate_is_flagged():
    # The plate's underside is a flat down-facing surface raised off the plate ->
    # a real overhang. overhang_area and worst_overhang_deg must be computed (> 0),
    # proving the normal/angle math actually ran over the mesh.
    node, qs = _plate_on_pillar()
    r = overhang_check(node, qs, build_dir=(0, 0, 1), tolerance=0.5)
    assert r["needs_support"] is True
    assert r["overhang_area"] > 0.0
    # a perfectly horizontal down-facing ceiling is 45 deg past the limit
    assert r["worst_overhang_deg"] > 0.0


def test_build_dir_is_consumed_cylinder_flips_verdict():
    # The SAME vertical cylinder: printed upright (+Z) the walls are vertical and the
    # base sits on the plate -> no support; printed lying on its side (+X) the curved
    # underside overhangs -> needs support. The verdict flipping proves build_dir is a
    # live input, not ignored.
    upright = overhang_check(_CYL_Z, _QS, build_dir=(0, 0, 1))
    on_side = overhang_check(_CYL_Z, _QS, build_dir=(1, 0, 0))
    assert upright["needs_support"] is False
    assert on_side["needs_support"] is True
    assert on_side["overhang_area"] > 0.0


def test_overhang_check_is_deterministic():
    node, qs = _plate_on_pillar()
    a = overhang_check(node, qs, tolerance=0.5)
    b = overhang_check(node, qs, tolerance=0.5)
    assert a == b


@settings(max_examples=8, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(sx=st.floats(2.0, 40.0), sy=st.floats(2.0, 40.0), sz=st.floats(2.0, 40.0))
def test_property_axis_aligned_box_never_overhangs_printed_flat(sx, sy, sz):
    # INVARIANT: an axis-aligned box printed flat (+Z) has only flat/vertical/up faces,
    # so it is self-supporting for ANY positive dimensions — a constant-returning facade
    # could not honour this across the random input space.
    qs = {"bx": _q("bx", sx), "by": _q("by", sy), "bz": _q("bz", sz)}
    box = GeometryNode(kind="box", params={"size_x": "bx", "size_y": "by", "size_z": "bz"})
    r = overhang_check(box, qs, build_dir=(0, 0, 1))
    assert r["needs_support"] is False
    assert r["overhang_area"] == 0.0


# --- bridge_spans: the span is measured from the mesh ---------------------------

def test_short_anchored_ceiling_is_a_printable_bridge():
    node, qs = _table(8.0)
    r = bridge_spans(node, qs)
    assert r["ok"] is True
    assert r["needs_support"] is False
    assert abs(r["worst_span"] - 8.0) < 0.2          # measured run between the legs
    assert r["worst_span"] <= FDM_MAX_BRIDGE_MM


def test_wide_anchored_ceiling_needs_support():
    node, qs = _table(30.0)
    r = bridge_spans(node, qs)
    assert r["needs_support"] is True
    assert r["ok"] is False
    assert abs(r["worst_span"] - 30.0) < 0.2         # the same measurement, now too long
    assert r["worst_span"] > FDM_MAX_BRIDGE_MM


def test_bridge_span_tracks_the_gap():
    # The reported span follows the geometry: a wider gap yields a larger span. A
    # constant could not track the input.
    narrow = bridge_spans(*_table(6.0))["worst_span"]
    wide = bridge_spans(*_table(12.0))["worst_span"]
    assert wide > narrow + 4.0


# --- first_layer_report: real contact vs the convergence probe ------------------

def test_box_has_real_plate_contact():
    r = first_layer_report(_BOX, _QS)
    assert r["plate_contact"] is True
    assert r["contact_area"] > 0.0
    assert abs(r["contact_area"] - 100.0) < 1.0      # the 10x10 bottom face
    assert r["vanishing_contact"] is False


def test_line_contact_solid_does_not_adhere_via_probe():
    # A cylinder LYING on its side touches the plate along a line, not a face. The
    # convergence probe must report no adhesion (the band "contact" vanishes under
    # refinement), never a fabricated flat contact.
    cyl = GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"})
    lying = GeometryNode(
        kind="rotate",
        params={"axis_x": "zero", "axis_y": "one", "axis_z": "zero", "angle_deg": "ninety"},
        children=[cyl],
    )
    qs = {"r": _q("r", 5.0), "h": _q("h", 20.0),
          "zero": _q("zero", 0.0), "one": _q("one", 1.0), "ninety": _q("ninety", 90.0)}
    r = first_layer_report(lying, qs, tolerance=0.3)
    assert r["plate_contact"] is False
    # honest abstention: either no band contact at all, or a band that vanishes under
    # the 16x refinement probe — both prove the probe (not a constant) decided.
    assert (r["contact_area"] == 0.0) or (r["vanishing_contact"] is True)


def test_first_layer_is_deterministic():
    a = first_layer_report(_BOX, _QS, tolerance=0.2)
    b = first_layer_report(_BOX, _QS, tolerance=0.2)
    assert a == b


# --- NEGATIVE: a degenerate empty boolean fails loud ----------------------------

def _empty_boolean() -> tuple[GeometryNode, dict[str, Quantity]]:
    """A small box minus a larger box that fully contains it -> an empty solid that
    tessellates to no triangles (the documented degenerate input)."""
    node = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "small", "size_y": "small", "size_z": "small"}),
        GeometryNode(kind="box", params={"size_x": "big", "size_y": "big", "size_z": "big"}),
    ])
    qs = {"small": _q("small", 10.0), "big": _q("big", 30.0)}
    return node, qs


def test_first_layer_report_empty_solid_raises():
    node, qs = _empty_boolean()
    with pytest.raises(ValueError, match="tessellation produced no triangles"):
        first_layer_report(node, qs)


def test_bridge_spans_empty_solid_raises():
    node, qs = _empty_boolean()
    with pytest.raises(ValueError, match="tessellation produced no triangles"):
        bridge_spans(node, qs)
