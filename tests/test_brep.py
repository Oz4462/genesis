"""Exact BREP geometry (OpenCASCADE) — the δ-1 AABB layer upgraded to exact.

brep.py translates the GENESIS CSG into real OpenCASCADE solids for exact volume,
validity and interference. cadquery/OCP is optional, so this test SKIPS when it is
absent; where present it pins:
  * exact volume agrees with the independent analytic geometry.volume_of, and is
    <= the conservative AABB volume (exact never exceeds the sound bound);
  * the capstone bracket is a valid solid;
  * EXACT interference beats AABB: two spheres whose bounding boxes overlap but
    whose solids do not are correctly reported as non-interfering — the case the
    conservative AABB layer cannot decide.

Offline, no LLM. Engine: OpenCASCADE via cadquery (optional).

Run:  pytest tests/test_brep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

pytest.importorskip("cadquery", reason="exact BREP needs the optional cadquery/OCP package")

from gen.brep import exact_volume, interferes, is_valid  # noqa: E402
from gen.core.state import GeometryNode, Quantity, ValueOrigin  # noqa: E402
from gen.verification.geometry import aabb_of, overlaps, volume_of  # noqa: E402


def _dec(qid, value):
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="x")


def test_exact_volume_agrees_with_analytic_and_is_within_aabb():
    from gen.demo import capstone_state
    spec = capstone_state().specification
    bracket = spec.components[0]
    q = {x.id: x for x in spec.quantities}

    exact = exact_volume(bracket.geometry, q)
    analytic = volume_of(bracket.geometry, q)
    assert analytic.exact
    assert abs(exact - analytic.value) < 1e-6        # two independent methods agree

    box = aabb_of(bracket.geometry, q)
    ex, ey, ez = box.extent
    assert exact <= ex * ey * ez + 1e-9              # exact never exceeds the AABB bound


def test_capstone_bracket_is_a_valid_solid():
    from gen.demo import capstone_state
    spec = capstone_state().specification
    bracket = spec.components[0]
    q = {x.id: x for x in spec.quantities}
    assert is_valid(bracket.geometry, q)


def test_overlapping_solids_interfere():
    q = {"s": _dec("s", 10.0), "off": _dec("off", 4.0), "z": _dec("z", 0.0)}
    a = GeometryNode(kind="box", params={"size_x": "s", "size_y": "s", "size_z": "s"})
    b = GeometryNode(kind="translate", params={"x": "off", "y": "off", "z": "z"},
                     children=[GeometryNode(kind="box",
                                            params={"size_x": "s", "size_y": "s", "size_z": "s"})])
    assert interferes(a, b, q)                        # boxes overlap by 6 mm each axis


def test_exact_interference_beats_conservative_aabb():
    # two r=2 spheres at (0,0,0) and (3,3,0): centre distance sqrt(18)=4.24 > 4,
    # so the SOLIDS are disjoint — but their AABBs ([-2,2]^3 and [1,5]x[1,5]x[-2,2])
    # DO overlap. The AABB layer cannot decide; exact BREP proves no interference.
    q = {"r": _dec("r", 2.0), "dx": _dec("dx", 3.0), "dy": _dec("dy", 3.0), "z0": _dec("z0", 0.0)}
    a = GeometryNode(kind="sphere", params={"radius": "r"})
    b = GeometryNode(kind="translate", params={"x": "dx", "y": "dy", "z": "z0"},
                     children=[GeometryNode(kind="sphere", params={"radius": "r"})])

    assert overlaps(aabb_of(a, q), aabb_of(b, q))     # AABBs overlap (conservative)
    assert not interferes(a, b, q)                    # but the solids do NOT (exact)
