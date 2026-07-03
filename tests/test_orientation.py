"""Orientation-dependent DFM — overhang / support detection (the delta-DFM upgrade).

orientation.py builds the OpenCASCADE solid, tessellates it, and flags down-facing
surfaces (within 45 deg of straight-down) that sit above the build plate - the
standard FDM support rule, which needs the geometry AND a build direction. The
decisive property is orientation-dependence: the SAME bracket needs no support
printed flat but needs support printed on its side. cadquery/OCP is optional, so
this test skips when it is absent.

Offline, no LLM. Engine: OpenCASCADE via cadquery (optional).

Run:  pytest tests/test_orientation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

pytest.importorskip("cadquery", reason="orientation DFM needs the optional cadquery/OCP package")

from gen.core.state import GeometryNode, Quantity, ValueOrigin  # noqa: E402
from gen.orientation import overhang_check  # noqa: E402


def _q(qid, v):
    return Quantity(id=qid, name=qid, value=v, unit="mm", origin=ValueOrigin.DECISION, rationale="x")


_QS = {"s": _q("s", 10.0), "r": _q("r", 5.0), "h": _q("h", 10.0)}
_BOX = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})
_SPHERE = GeometryNode(kind="sphere", params={"radius": "r"})
_CYL_Z = GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"})


def test_box_needs_no_support():
    # a box on the plate: bottom is plate contact, sides vertical, top up
    assert not overhang_check(_BOX, _QS)["needs_support"]


def test_cylinder_along_build_dir_needs_no_support():
    # a vertical cylinder: walls are vertical, the bottom cap is on the plate
    assert not overhang_check(_CYL_Z, _QS)["needs_support"]


def test_sphere_needs_support():
    # a sphere's bottom cap (below ~54 deg latitude) overhangs the plate
    r = overhang_check(_SPHERE, _QS)
    assert r["needs_support"] and r["overhang_area"] > 0.0


def test_orientation_changes_the_verdict():
    from gen.demo import capstone_state
    spec = capstone_state().specification
    bracket = spec.components[0].geometry
    q = {x.id: x for x in spec.quantities}
    flat = overhang_check(bracket, q, build_dir=(0, 0, 1))     # printed lying flat
    on_side = overhang_check(bracket, q, build_dir=(1, 0, 0))  # printed on its side
    assert not flat["needs_support"]                           # flat: through-hole is vertical
    assert on_side["needs_support"]                            # sideways: the hole overhangs


def test_is_deterministic():
    a = overhang_check(_SPHERE, _QS, tolerance=0.1)
    b = overhang_check(_SPHERE, _QS, tolerance=0.1)
    assert a == b


# --- support volume estimate ---------------------------------------------------

def test_no_overhang_means_no_support_volume():
    assert overhang_check(_BOX, _QS)["support_volume"] == 0.0


def test_support_volume_is_the_column_under_the_overhang():
    # a 20x20x2 plate (z in [10,12]) on a 4x4x20 pillar (z in [-10,10]): the plate's
    # bottom overhangs everywhere except over the pillar -> overhang area 400-16=384,
    # a column 20 mm tall (down to the plate at z=-10) under it.
    pillar = GeometryNode(kind="box", params={"size_x": "p", "size_y": "p", "size_z": "ph"})
    plate = GeometryNode(kind="translate", params={"x": "z0", "y": "z0", "z": "tz"},
                         children=[GeometryNode(kind="box",
                                                params={"size_x": "pl", "size_y": "pl", "size_z": "pt"})])
    solid = GeometryNode(kind="union", children=[pillar, plate])
    qs = {"p": _q("p", 4.0), "ph": _q("ph", 20.0), "pl": _q("pl", 20.0),
          "pt": _q("pt", 2.0), "z0": _q("z0", 0.0), "tz": _q("tz", 11.0)}
    density = 0.2
    r = overhang_check(solid, qs, tolerance=0.5, support_density=density)
    # support volume = overhang_area × column_height(20) × density, self-consistent
    assert abs(r["support_volume"] - r["overhang_area"] * 20.0 * density) < 1.0
    assert r["overhang_area"] > 380.0                  # ~ 400 - 16


def test_support_volume_scales_with_density():
    sparse = overhang_check(_SPHERE, _QS, support_density=0.1)["support_volume"]
    dense = overhang_check(_SPHERE, _QS, support_density=0.4)["support_volume"]
    assert abs(dense - 4.0 * sparse) < 1e-9            # linear in density


# --- first layer: adhesion + elephant foot --------------------------------------

from gen.orientation import bridge_spans, first_layer_report  # noqa: E402


def test_box_first_layer_contact_and_elephant_foot_risk():
    r = first_layer_report(_BOX, _QS)
    assert r["plate_contact"]
    assert abs(r["contact_area"] - 100.0) < 1.0        # the 10x10 bottom face
    assert abs(r["footprint"][0] - 10.0) < 0.1 and abs(r["footprint"][1] - 10.0) < 0.1
    assert abs(r["height"] - 10.0) < 1e-6
    # vertical walls meet the plate at 90 deg -> the squashed first layers bulge
    assert r["sharp_base_edge"] and r["elephant_foot_risk"]
    assert r["recommended_base_chamfer"] == 0.3


def test_sphere_has_no_plate_contact_at_all():
    r = first_layer_report(_SPHERE, _QS)
    assert not r["plate_contact"] and r["contact_area"] == 0.0
    assert not r["sharp_base_edge"] and not r["elephant_foot_risk"]
    assert r["recommended_base_chamfer"] == 0.0


# --- bridges: the refinement of the blanket support rule ------------------------

def _table(gap: float, leg: float = 5.0, depth: float = 20.0,
           leg_h: float = 10.0, top_t: float = 5.0):
    """Two legs + a top plate; the underside between the legs spans `gap` [mm]."""
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


def test_table_30mm_gap_is_too_long_to_bridge():
    r = bridge_spans(*_table(30.0))
    assert r["needs_support"] and not r["ok"]
    assert abs(r["worst_span"] - 30.0) < 0.1           # anchored at the legs, 30 mm run
    (region,) = r["regions"]
    assert sum(region["anchored_sides"].values()) == 2  # one opposite pair (the legs)


def test_table_8mm_gap_is_a_printable_bridge():
    r = bridge_spans(*_table(8.0))
    assert r["ok"] and not r["needs_support"]
    assert abs(r["worst_span"] - 8.0) < 0.1


def test_pocket_ceiling_bridges_across_the_short_side():
    # 20x20x10 block with an 8x16x6 pocket opening DOWNWARD: the pocket ceiling is
    # anchored on all four sides -> bridgeable across the 8 mm direction. The blanket
    # overhang rule flags it; the bridge layer honestly clears it.
    qs = {k: _q(k, v) for k, v in {
        "bx": 20.0, "by": 20.0, "bz": 10.0, "cx": 8.0, "cy": 16.0, "cz": 6.0,
        "zero": 0.0, "cdz": -2.0,
    }.items()}
    node = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "bx", "size_y": "by", "size_z": "bz"}),
        GeometryNode(kind="translate", params={"x": "zero", "y": "zero", "z": "cdz"},
                     children=[GeometryNode(kind="box",
                                            params={"size_x": "cx", "size_y": "cy",
                                                    "size_z": "cz"})]),
    ])
    r = bridge_spans(node, qs)
    assert r["ok"]
    (region,) = r["regions"]
    assert all(region["anchored_sides"].values())      # all four sides anchored
    assert abs(region["span"] - 8.0) < 0.1             # the SHORT direction
    assert overhang_check(node, qs)["needs_support"]   # the blanket rule still flags it


def test_cantilever_ceiling_cannot_be_bridged():
    # plate on ONE end pillar: the underside is anchored on a single side only --
    # that is a cantilever, not a bridge, regardless of its size.
    qs = {k: _q(k, v) for k, v in {
        "px": 4.0, "depth": 20.0, "ph": 10.0, "tx": 20.0, "tt": 2.0,
        "pdx": -8.0, "zero": 0.0, "tz": 6.0,
    }.items()}
    node = GeometryNode(kind="union", children=[
        GeometryNode(kind="translate", params={"x": "pdx", "y": "zero", "z": "zero"},
                     children=[GeometryNode(kind="box",
                                            params={"size_x": "px", "size_y": "depth",
                                                    "size_z": "ph"})]),
        GeometryNode(kind="translate", params={"x": "zero", "y": "zero", "z": "tz"},
                     children=[GeometryNode(kind="box",
                                            params={"size_x": "tx", "size_y": "depth",
                                                    "size_z": "tt"})]),
    ])
    r = bridge_spans(node, qs)
    assert r["needs_support"]
    (region,) = r["regions"]
    assert region["span"] is None                      # no opposite anchored pair
    assert r["worst_span"] == float("inf")


def test_bridge_and_first_layer_are_deterministic():
    node, qs = _table(8.0)
    assert bridge_spans(node, qs, tolerance=0.2) == bridge_spans(node, qs, tolerance=0.2)
    assert (first_layer_report(_BOX, _QS, tolerance=0.2)
            == first_layer_report(_BOX, _QS, tolerance=0.2))
