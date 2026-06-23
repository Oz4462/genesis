"""Depth-audit characterization tests for mesh_integrity.py (δ STL sliceability proof).

Proves that stl_integrity_check implements *exact* topology and divergence math
(directed-edge watertight test, Euler-Poincaré chi=V-E+F, signed volume via
1/6·∑a·(b×c)), not a heuristic that always returns ok=True.

Baseline: a hand-built watertight, outward-wound unit cube (exactly 12 triangles,
8 shared vertices, true volume = 1.0).

Facade-killer:
- output (flags + volume + chi + issues) changes correctly under input mutations
  (remove face, reverse all windings, scale)
- every documented ValueError guard fires exactly
- Hypothesis property confirms scale-invariance of topology + cubic volume scaling

The test constructs its own STL text; no external CAD kernel required.
Offline, deterministic, stdlib + hypothesis only.

Run:  pytest tests/test_mesh_integrity_characterization.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.mesh_integrity import stl_integrity_check  # noqa: E402


def _build_cube_tris():
    """Return list of 12 outward-wound triangles for the [0,1]^3 unit cube."""
    v000 = (0.0, 0.0, 0.0)
    v100 = (1.0, 0.0, 0.0)
    v010 = (0.0, 1.0, 0.0)
    v001 = (0.0, 0.0, 1.0)
    v110 = (1.0, 1.0, 0.0)
    v101 = (1.0, 0.0, 1.0)
    v011 = (0.0, 1.0, 1.0)
    v111 = (1.0, 1.0, 1.0)
    # Each pair defines one quad split into two tris; order chosen so that
    # right-hand rule points normals outward (positive contribution to signed vol).
    tris = [
        # +z (top)
        (v001, v101, v111), (v001, v111, v011),
        # -z (bottom)
        (v000, v010, v110), (v000, v110, v100),
        # +y
        (v010, v011, v111), (v010, v111, v110),
        # -y
        (v000, v100, v101), (v000, v101, v001),
        # +x
        (v100, v110, v111), (v100, v111, v101),
        # -x
        (v000, v001, v011), (v000, v011, v010),
    ]
    return tris


def _stl(tris):
    """Minimal ASCII STL emitter (no normals, sufficient for the parser)."""
    chunks = ["solid unitcube\n"]
    for a, b, c in tris:
        chunks.append("  facet normal 0 0 0\n    outer loop\n")
        for p in (a, b, c):
            chunks.append(f"      vertex {p[0]} {p[1]} {p[2]}\n")
        chunks.append("    endloop\n  endfacet\n")
    chunks.append("endsolid unitcube\n")
    return "".join(chunks)


def _cube_stl():
    return _stl(_build_cube_tris())


# --------------------------------------------------------------------------- #
# (1) Valid unit cube baseline — all headline predicates must hold exactly.
# --------------------------------------------------------------------------- #

def test_valid_unit_cube_is_exactly_watertight_outward_genus_zero():
    stl = _cube_stl()
    r = stl_integrity_check(stl)

    assert r["ok"] is True
    assert r["watertight"] is True
    assert r["consistent_winding"] is True
    assert r["euler_characteristic"] == 2
    assert r["genus"] == 0
    assert r["volume_positive"] is True
    # Divergence theorem must recover the geometric volume of the unit cube.
    assert math.isclose(r["volume"], 1.0, abs_tol=1e-9)
    assert r["n_facets"] == 12
    assert r["n_vertices"] == 8
    assert r["n_degenerate"] == 0
    # The exact counts that drive the decisions are observable (see source edit
    # below that surfaces them for the proof; they are already computed exactly).
    assert r["open_edges"] == 0
    assert r.get("duplicated", 0) == 0
    assert r["issues"] == []


# --------------------------------------------------------------------------- #
# (2) Deleting one triangle produces a genuine hole: open_edges > 0, not ok.
# --------------------------------------------------------------------------- #

def test_deleting_one_triangle_yields_hole_not_watertight_and_issues_entry():
    tris = _build_cube_tris()
    hole_stl = _stl(tris[:-1])  # remove exactly one facet
    r = stl_integrity_check(hole_stl)

    assert r["ok"] is False
    assert r["watertight"] is False
    assert r["open_edges"] > 0  # the exact count produced by the edge walk
    assert any("open" in i for i in r["issues"])
    assert any("hole" in i.lower() for i in r["issues"])


# --------------------------------------------------------------------------- #
# (3) Reversing *all* windings yields inside-out solid (volume < 0, ok=False)
#     while topology (watertight + consistent) stays perfect — volume sign
#     is the only detector.
# --------------------------------------------------------------------------- #

def test_full_winding_reversal_produces_negative_volume_and_fails_ok():
    tris = _build_cube_tris()
    inside_out = [(a, c, b) for a, b, c in tris]
    r = stl_integrity_check(_stl(inside_out))

    assert r["volume"] < 0.0
    assert r["volume_positive"] is False
    assert r["ok"] is False
    # The surface is still topologically perfect (just oriented inward).
    assert r["watertight"] is True
    assert r["consistent_winding"] is True
    assert math.isclose(abs(r["volume"]), 1.0, abs_tol=1e-9)


# --------------------------------------------------------------------------- #
# (4) Documented ValueError guards fire loud (no silent partial parse).
# --------------------------------------------------------------------------- #

def test_non_multiple_of_three_vertices_raises_valueerror():
    # 2 vertices in one "triangle" — parser must reject before any verdict.
    bad = (
        "solid bad\n"
        "  facet normal 0 0 0\n"
        "    outer loop\n"
        "      vertex 0 0 0\n"
        "      vertex 1 0 0\n"
        "    endloop\n"
        "  endfacet\n"
        "endsolid bad\n"
    )
    with pytest.raises(ValueError, match="multiple of three"):
        stl_integrity_check(bad)


def test_text_with_no_vertices_raises_valueerror():
    with pytest.raises(ValueError, match="no vertices found"):
        stl_integrity_check("solid empty\nendsolid empty\n")


# --------------------------------------------------------------------------- #
# Property-based invariants (Hypothesis) — scale and winding reversal.
# --------------------------------------------------------------------------- #

@settings(max_examples=40, deadline=None)
@given(scale=st.floats(min_value=0.1, max_value=50.0))
def test_property_uniform_scale_preserves_topology_and_cubic_volume(scale):
    """INVARIANT: a uniformly scaled watertight outward cube must remain
    watertight/consistent/chi=2/genus=0/volume_positive, and the signed volume
    must be exactly scale**3 (within fp tol). This proves the divergence
    integral and the topology walk are genuinely driven by vertex coordinates,
    not by a hardcoded "unit cube ok" path."""
    tris = _build_cube_tris()
    scaled_tris = [
        tuple((x * scale, y * scale, z * scale) for x, y, z in tri)  # type: ignore[misc]
        for tri in tris
    ]
    r = stl_integrity_check(_stl(scaled_tris))

    assert r["watertight"] is True
    assert r["consistent_winding"] is True
    assert r["ok"] is True
    assert r["euler_characteristic"] == 2
    assert r["genus"] == 0
    assert r["volume_positive"] is True
    assert math.isclose(r["volume"], scale ** 3, rel_tol=1e-9, abs_tol=1e-12)


@settings(max_examples=5, deadline=None)
@given(_=st.integers(min_value=0, max_value=0))  # dummy to satisfy @given contract
def test_property_full_winding_reversal_negates_volume_but_keeps_watertight(_):
    """INVARIANT: reversing orientation of every triangle on a closed manifold
    must negate the signed volume while leaving the watertight/consistent_winding
    predicates unchanged (they only look at edge pairing, not direction of the
    traversal)."""
    tris = _build_cube_tris()
    orig_vol = stl_integrity_check(_stl(tris))["volume"]
    flipped = [(a, c, b) for a, b, c in tris]
    r = stl_integrity_check(_stl(flipped))
    assert math.isclose(r["volume"], -orig_vol, abs_tol=1e-12)
    assert r["watertight"] is True
    assert r["consistent_winding"] is True
    assert r["volume_positive"] is False
