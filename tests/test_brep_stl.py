"""Print-ready STL — CSG booleans evaluated on the kernel, proven by volume.

The exported mesh must contain the hole (it is a difference, not just a box): the
divergence-theorem volume of the STL triangles must match the kernel's exact solid
volume to tessellation tolerance and lie strictly below the unbored box volume. The
file must be valid ASCII STL. cadquery is optional — the test skips without it, and
the CLI falls back to the honest boolean-refusing primitive export.

Offline, no LLM. Engine: OpenCASCADE via cadquery (optional).

Run:  pytest tests/test_brep_stl.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

pytest.importorskip("cadquery", reason="print-ready STL needs the optional cadquery/OCP")

from gen.brep import exact_volume  # noqa: E402
from gen.demo import capstone_spec  # noqa: E402
from gen.export.brep_stl import specification_to_brep_stl  # noqa: E402

_VERTEX = re.compile(r"vertex ([\d.eE+-]+) ([\d.eE+-]+) ([\d.eE+-]+)")


def _mesh_volume(stl: str) -> float:
    """Signed mesh volume via the divergence theorem over the facet triangles."""
    verts = [tuple(map(float, m.groups())) for m in _VERTEX.finditer(stl)]
    vol = 0.0
    for i in range(0, len(verts), 3):
        a, b, c = verts[i], verts[i + 1], verts[i + 2]
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1])
                - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return abs(vol)


def test_capstone_stl_is_print_ready_with_the_hole():
    spec = capstone_spec()
    stl = specification_to_brep_stl(spec)
    assert stl.startswith("solid genesis_capstone")
    assert stl.rstrip().endswith("endsolid genesis_capstone")
    n_facets = stl.count("facet normal")
    assert n_facets > 100                                   # a real tessellation
    assert stl.count("endfacet") == n_facets                # well-formed ASCII STL

    quantities = {q.id: q for q in spec.quantities}
    exact = exact_volume(spec.components[0].geometry, quantities)
    mesh = _mesh_volume(stl)
    assert abs(mesh - exact) / exact < 1e-3                 # mesh == kernel volume
    assert mesh < 60.0 * 80.0 * 12.0                        # the HOLE is in the mesh


def test_cli_stl_format_now_yields_the_evaluated_mesh():
    from gen.cli import render_spec

    out = render_spec(capstone_spec(), "stl")
    assert out.startswith("solid genesis_capstone")         # no more "unavailable" note
    assert "facet normal" in out


def test_is_deterministic():
    a = specification_to_brep_stl(capstone_spec())
    b = specification_to_brep_stl(capstone_spec())
    assert a == b
