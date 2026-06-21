"""Geometry verification — the built CAD must match what the spec analytically implies.

The exact BREP solid is cross-checked against the independent analytic layer: a real part
(the capstone bracket) passes (valid, non-zero, volume and extents agree); a sphere passes with
an EXACT volume match (the cross-check that would have caught the old hemisphere bug, half the
volume); a degenerate CSG that removes all material fails (zero volume). cadquery/OCP is
optional, so the test skips when it is absent.

Offline, no LLM. Engine: OpenCASCADE via cadquery (optional).

Run:  pytest tests/test_geometry_verification.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

pytest.importorskip("cadquery", reason="geometry verification needs the optional cadquery/OCP")

from gen.core.state import GeometryNode, Quantity, ValueOrigin  # noqa: E402
from gen.demo import capstone_spec  # noqa: E402
from gen.geometry_verification import verify_geometry  # noqa: E402


def _q(qid, v):
    return Quantity(id=qid, name=qid, value=v, unit="mm", origin=ValueOrigin.DECISION, rationale="x")


def test_real_bracket_geometry_matches_the_spec():
    spec = capstone_spec()
    node = spec.components[0].geometry
    quantities = {x.id: x for x in spec.quantities}
    r = verify_geometry(node, quantities)
    assert r["ok"]
    assert r["valid"] and r["nonzero_volume"]
    assert r["volume_ok"] and r["extent_ok"]
    assert tuple(round(e, 2) for e in r["brep_extent"]) == (60.0, 80.0, 12.0)   # declared w,h,t


def test_sphere_volume_matches_exactly_the_hemisphere_bug_guard():
    node = GeometryNode(kind="sphere", params={"radius": "r"})
    r = verify_geometry(node, {"r": _q("r", 5.0)})
    assert r["ok"] and r["analytic_exact"]
    # exact 4/3 pi r^3 = 523.5987...; a hemisphere (half) would fail this cross-check
    assert math.isclose(r["brep_volume"], 4.0 / 3.0 * math.pi * 125.0, rel_tol=1e-6)
    assert math.isclose(r["brep_volume"], r["analytic_volume"], rel_tol=1e-9)


def test_degenerate_csg_that_removes_everything_fails():
    # a 10 mm box minus a covering 20 mm box -> empty solid, zero volume
    node = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "a", "size_y": "a", "size_z": "a"}),
        GeometryNode(kind="box", params={"size_x": "b", "size_y": "b", "size_z": "b"}),
    ])
    r = verify_geometry(node, {"a": _q("a", 10.0), "b": _q("b", 20.0)})
    assert not r["ok"] and not r["nonzero_volume"]


def test_is_deterministic():
    node = GeometryNode(kind="sphere", params={"radius": "r"})
    a = verify_geometry(node, {"r": _q("r", 3.0)})
    b = verify_geometry(node, {"r": _q("r", 3.0)})
    assert a == b
