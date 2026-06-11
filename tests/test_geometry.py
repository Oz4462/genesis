"""Tests for the AABB algebra behind Phase δ — exact, sound, no LLM.

Pins the centered-primitive convention, the union envelope / intersection overlap
math, translation, and the per-axis overlap test that makes δ sound (no false
positives). See PHASE_DELTA.md §1/§3/§8.

Run:  pytest tests/test_geometry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

import math  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.core.state import GeometryNode, Quantity, ValueOrigin  # noqa: E402
from gen.verification.geometry import Aabb, aabb_of, overlaps, volume_of  # noqa: E402


def _q(qid: str, value: float) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="t")


def _qs(*pairs) -> dict[str, Quantity]:
    return {qid: _q(qid, v) for qid, v in pairs}


# --- primitives are centered at the origin ------------------------------------

def test_box_is_centered():
    q = _qs(("x", 60.0), ("y", 80.0), ("z", 6.0))
    box = aabb_of(GeometryNode(kind="box", params={"size_x": "x", "size_y": "y", "size_z": "z"}), q)
    assert box.extent == (60.0, 80.0, 6.0)
    assert (box.min_x, box.max_x) == (-30.0, 30.0)


def test_cylinder_axis_is_z():
    q = _qs(("r", 2.5), ("h", 10.0))
    cyl = aabb_of(GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"}), q)
    assert cyl.extent == (5.0, 5.0, 10.0)          # diameter x diameter x height


def test_sphere_extent():
    q = _qs(("r", 3.0))
    sph = aabb_of(GeometryNode(kind="sphere", params={"radius": "r"}), q)
    assert sph.extent == (6.0, 6.0, 6.0)


# --- translate / union / difference / intersection ----------------------------

def test_translate_shifts_box():
    q = _qs(("s", 2.0), ("dx", 10.0), ("dy", 0.0), ("dz", 0.0))
    geom = GeometryNode(kind="translate", params={"x": "dx", "y": "dy", "z": "dz"},
                        children=[GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})])
    box = aabb_of(geom, q)
    assert (box.min_x, box.max_x) == (9.0, 11.0)   # centered ±1 then shifted +10


def test_union_is_envelope():
    q = _qs(("s", 2.0), ("dx", 10.0), ("z0", 0.0))
    a = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})
    b = GeometryNode(kind="translate", params={"x": "dx", "y": "z0", "z": "z0"}, children=[a])
    union = aabb_of(GeometryNode(kind="union", children=[a, b]), q)
    assert (union.min_x, union.max_x) == (-1.0, 11.0)   # envelope spans both


def test_difference_bound_is_the_minuend():
    q = _qs(("big", 10.0), ("small", 2.0))
    body = GeometryNode(kind="box", params={"size_x": "big", "size_y": "big", "size_z": "big"})
    hole = GeometryNode(kind="cylinder", params={"radius": "small", "height": "big"})
    diff = aabb_of(GeometryNode(kind="difference", children=[body, hole]), q)
    assert diff.extent == (10.0, 10.0, 10.0)        # subtracting cannot grow it


def test_intersection_overlap_region():
    q = _qs(("s", 4.0), ("dx", 2.0), ("z0", 0.0))
    a = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})  # ±2
    b = GeometryNode(kind="translate", params={"x": "dx", "y": "z0", "z": "z0"}, children=[a])  # ±2 +2
    inter = aabb_of(GeometryNode(kind="intersection", children=[a, b]), q)
    assert (inter.min_x, inter.max_x) == (0.0, 2.0)  # overlap of [-2,2] and [0,4]


def test_disjoint_intersection_is_empty():
    q = _qs(("s", 2.0), ("far", 100.0), ("z0", 0.0))
    a = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})
    b = GeometryNode(kind="translate", params={"x": "far", "y": "z0", "z": "z0"}, children=[a])
    inter = aabb_of(GeometryNode(kind="intersection", children=[a, b]), q)
    assert inter.empty


# --- the overlap test (soundness primitive) -----------------------------------

def test_overlaps_requires_every_axis():
    a = Aabb(0, 0, 0, 2, 2, 2)
    near = Aabb(1, 1, 1, 3, 3, 3)
    far_x = Aabb(5, 0, 0, 7, 2, 2)
    assert overlaps(a, near)
    assert not overlaps(a, far_x)        # disjoint on x -> no overlap
    touching = Aabb(2, 0, 0, 4, 2, 2)
    assert overlaps(a, touching)         # shared face counts (closed intervals)


def test_empty_box_overlaps_nothing():
    a = Aabb(0, 0, 0, 2, 2, 2)
    empty = Aabb(0, 0, 0, 0, 0, 0, empty=True)
    assert not overlaps(a, empty)


# --- loud failure -------------------------------------------------------------

def test_unknown_kind_raises():
    with pytest.raises(GeometryError):
        aabb_of(GeometryNode(kind="torus", params={}), {})


def test_missing_param_raises():
    with pytest.raises(GeometryError):
        aabb_of(GeometryNode(kind="sphere", params={}), {})


def test_absent_quantity_raises():
    with pytest.raises(GeometryError):
        aabb_of(GeometryNode(kind="sphere", params={"radius": "ghost"}), {})


# --- volume: exact where provable, else a sound upper bound -------------------

def test_primitive_volumes_are_exact():
    q = _qs(("x", 2.0), ("y", 3.0), ("z", 4.0), ("r", 5.0), ("h", 6.0))
    box = volume_of(GeometryNode(kind="box", params={"size_x": "x", "size_y": "y", "size_z": "z"}), q)
    assert box.exact and box.value == 24.0
    cyl = volume_of(GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"}), q)
    assert cyl.exact and cyl.value == pytest.approx(math.pi * 25 * 6)
    sph = volume_of(GeometryNode(kind="sphere", params={"radius": "r"}), q)
    assert sph.exact and sph.value == pytest.approx((4 / 3) * math.pi * 125)


def test_translate_preserves_volume():
    q = _qs(("s", 2.0), ("d", 10.0), ("z0", 0.0))
    geom = GeometryNode(kind="translate", params={"x": "d", "y": "z0", "z": "z0"},
                        children=[GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})])
    assert volume_of(geom, q).value == 8.0


def test_hole_in_block_is_exact_difference():
    # box 60x80x6 minus a centered through-hole cylinder r=2.25 h=6 -> exact
    q = _qs(("w", 60.0), ("h", 80.0), ("t", 6.0), ("r", 2.25))
    geom = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "w", "size_y": "h", "size_z": "t"}),
        GeometryNode(kind="cylinder", params={"radius": "r", "height": "t"}),
    ])
    vol = volume_of(geom, q)
    assert vol.exact
    assert vol.value == pytest.approx(60 * 80 * 6 - math.pi * 2.25 ** 2 * 6)


def test_disjoint_union_is_exact_sum():
    q = _qs(("s", 2.0), ("far", 100.0), ("z0", 0.0))
    a = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})
    b = GeometryNode(kind="translate", params={"x": "far", "y": "z0", "z": "z0"}, children=[a])
    vol = volume_of(GeometryNode(kind="union", children=[a, b]), q)
    assert vol.exact and vol.value == 16.0          # two disjoint 2x2x2 boxes


def test_overlapping_union_is_upper_bound_not_exact():
    q = _qs(("s", 4.0), ("near", 1.0), ("z0", 0.0))
    a = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})
    b = GeometryNode(kind="translate", params={"x": "near", "y": "z0", "z": "z0"}, children=[a])
    vol = volume_of(GeometryNode(kind="union", children=[a, b]), q)
    assert not vol.exact
    assert vol.value == 128.0                        # Σ parts (sound upper bound)
    assert "upper bound" in vol.note


def test_uncontained_difference_is_upper_bound():
    # the tool sticks out of the body -> not provably contained -> inexact bound
    q = _qs(("s", 4.0), ("r", 1.0), ("big", 50.0), ("far", 3.0), ("z0", 0.0))
    geom = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"}),
        GeometryNode(kind="translate", params={"x": "far", "y": "z0", "z": "z0"},
                     children=[GeometryNode(kind="cylinder", params={"radius": "r", "height": "big"})]),
    ])
    vol = volume_of(geom, q)
    assert not vol.exact
    assert vol.value == 64.0                         # vol of minuend (upper bound)


def test_difference_with_non_box_minuend_is_inexact():
    # minuend is a cylinder (solid != AABB) -> can't prove containment -> inexact
    q = _qs(("r", 10.0), ("h", 10.0), ("sr", 1.0))
    geom = GeometryNode(kind="difference", children=[
        GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"}),
        GeometryNode(kind="sphere", params={"radius": "sr"}),
    ])
    vol = volume_of(geom, q)
    assert not vol.exact
    assert vol.value == pytest.approx(math.pi * 100 * 10)   # vol of the cylinder minuend
