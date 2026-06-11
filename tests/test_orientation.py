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
