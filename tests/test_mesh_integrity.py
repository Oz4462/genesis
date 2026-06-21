"""STL mesh integrity — watertightness, winding, Euler characteristic, orientation.

Exact anchors, no heuristics: the unit tetrahedron has V=4, E=6, F=4 (chi = 2,
genus 0) and volume exactly 1/6; removing a facet opens edges; flipping ONE facet
breaks the winding; flipping ALL facets leaves a perfectly watertight mesh whose
signed volume is exactly negative — the inside-out solid only the volume test
catches. The capstone bracket STL (kernel-evaluated, one through-hole) must come
out genus 1 (chi = 0) — topology proving the hole survived into the mesh.

Offline, no LLM. stdlib only; the capstone case is cadquery-gated.

Run:  pytest tests/test_mesh_integrity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.mesh_integrity import stl_integrity_check  # noqa: E402

ORIG = (0.0, 0.0, 0.0)
X = (1.0, 0.0, 0.0)
Y = (0.0, 1.0, 0.0)
Z = (0.0, 0.0, 1.0)

# Outward-wound unit tetrahedron (each face's normal points away from the body).
TETRA_FACES = [(ORIG, Y, X), (ORIG, X, Z), (ORIG, Z, Y), (X, Y, Z)]


def _stl(faces) -> str:
    chunks = ["solid t\n"]
    for a, b, c in faces:
        chunks.append("  facet normal 0 0 0\n    outer loop\n")
        for v in (a, b, c):
            chunks.append(f"      vertex {v[0]} {v[1]} {v[2]}\n")
        chunks.append("    endloop\n  endfacet\n")
    chunks.append("endsolid t\n")
    return "".join(chunks)


def test_tetrahedron_exact_topology_and_volume():
    r = stl_integrity_check(_stl(TETRA_FACES))
    assert r["ok"] and r["issues"] == []
    assert (r["n_vertices"], r["n_edges"], r["n_facets"]) == (4, 6, 4)
    assert r["euler_characteristic"] == 2 and r["genus"] == 0
    assert r["watertight"] and r["consistent_winding"]
    assert r["volume"] == pytest.approx(1.0 / 6.0)


def test_missing_facet_means_holes():
    r = stl_integrity_check(_stl(TETRA_FACES[:-1]))
    assert not r["ok"] and not r["watertight"]
    assert any("open" in i for i in r["issues"])


def test_one_flipped_facet_breaks_winding():
    a, b, c = TETRA_FACES[-1]
    r = stl_integrity_check(_stl(TETRA_FACES[:-1] + [(a, c, b)]))
    assert not r["ok"] and not r["consistent_winding"]


def test_inside_out_solid_only_the_volume_test_catches():
    flipped = [(a, c, b) for a, b, c in TETRA_FACES]
    r = stl_integrity_check(_stl(flipped))
    assert r["watertight"] and r["consistent_winding"]   # topologically perfect...
    assert r["volume"] == pytest.approx(-1.0 / 6.0)      # ...but inside-out
    assert not r["volume_positive"] and not r["ok"]


def test_degenerate_facet_is_flagged():
    r = stl_integrity_check(_stl(TETRA_FACES + [(ORIG, ORIG, X)]))
    assert r["n_degenerate"] == 1 and not r["ok"]


def test_unparseable_raises():
    with pytest.raises(ValueError):
        stl_integrity_check("solid empty\nendsolid empty\n")
    with pytest.raises(ValueError):
        stl_integrity_check(_stl(TETRA_FACES).replace("vertex 1.0 0.0 0.0\n", "", 1))


def test_capstone_bracket_mesh_is_genus_one():
    pytest.importorskip("cadquery", reason="kernel STL needs cadquery/OCP")
    from gen.brep import exact_volume
    from gen.demo import capstone_spec
    from gen.export.brep_stl import specification_to_brep_stl

    spec = capstone_spec()
    r = stl_integrity_check(specification_to_brep_stl(spec))
    assert r["ok"], r["issues"]
    assert r["euler_characteristic"] == 0 and r["genus"] == 1   # the hole, in topology
    quantities = {q.id: q for q in spec.quantities}
    exact = exact_volume(spec.components[0].geometry, quantities)
    assert r["volume"] == pytest.approx(exact, rel=1e-3)
