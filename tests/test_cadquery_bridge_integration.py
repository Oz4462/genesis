"""Exact OCCT BREP via the isolated cad-venv subprocess bridge.

cadquery cannot live in the main GENESIS venv (it downgrades numpy), so the exact
OpenCASCADE path runs in /home/genesis/.venv-cad and is reached through
``cad.cadquery_bridge`` (serialise CSG -> run cad/cadquery_worker.py -> parse).
This test exercises that REAL subprocess path:

  * exact boolean volume — a box bored by a cylinder is < the box volume AND equals
    the analytic ``box - π r² h`` to the kernel's precision (the booleans the
    conservative AABB layer cannot evaluate);
  * the bored solid is a valid solid (BRepCheck);
  * EXACT interference beats AABB — two boxes whose bounding boxes touch-overlap but
    whose solids are disjoint are reported non-interfering;
  * print-ready STL of the bored solid has facets and a single solid block;
  * STEP (AP214) export produces a real ISO-10303 file (the lossless interchange the
    STL/AABB paths cannot give);
  * brep.py's public API (exact_volume/is_valid/interferes) routes through the bridge
    and agrees with the analytic geometry.volume_of on a primitive.

Named ``*_integration.py`` (spawns a subprocess) and SKIPS when the cad venv is
absent — on the GENESIS box it is present, so this PASSES.

Run:  PYTHONPATH=src .venv/bin/python -m pytest tests/test_cadquery_bridge_integration.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.cad import cadquery_bridge as br  # noqa: E402
from gen.core.errors import GeometryError  # noqa: E402
from gen.core.state import GeometryNode, Quantity, ValueOrigin  # noqa: E402

if not br.cad_available():
    pytest.skip(
        f"isolated cad venv not available at {br.cad_python()!r}",
        allow_module_level=True,
    )


def _q(qid: str, value: float) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="x")


def _bored_box():
    """A 10mm cube bored through-Z by a r=2 cylinder — a real CSG difference."""
    quant = {
        "sx": _q("sx", 10), "sy": _q("sy", 10), "sz": _q("sz", 10),
        "r": _q("r", 2.0), "h": _q("h", 12.0),
    }
    box = GeometryNode(kind="box", params={"size_x": "sx", "size_y": "sy", "size_z": "sz"})
    cyl = GeometryNode(kind="cylinder", params={"radius": "r", "height": "h"})
    bored = GeometryNode(kind="difference", params={}, children=[box, cyl])
    return bored, box, quant


def test_exact_boolean_volume_matches_analytic_and_below_box():
    bored, box, quant = _bored_box()
    box_vol = br.exact_volume(box, quant)
    bored_vol = br.exact_volume(bored, quant)
    assert math.isclose(box_vol, 1000.0, rel_tol=1e-9)
    # analytic: cube minus the cylindrical bore through the full thickness
    expected = 1000.0 - math.pi * (2.0 ** 2) * 10.0
    assert math.isclose(bored_vol, expected, rel_tol=1e-4), (bored_vol, expected)
    assert bored_vol < box_vol  # the hole is really in the solid


def test_bored_solid_is_valid():
    bored, _box, quant = _bored_box()
    assert br.is_valid(bored, quant) is True


def test_exact_interference_beats_aabb():
    """Two unit cubes side by side, the second translated so their AABBs share a face
    but the solids only touch (zero-volume contact) -> NOT interfering by exact test."""
    quant = {
        "sx": _q("sx", 10), "sy": _q("sy", 10), "sz": _q("sz", 10),
        "dx": _q("dx", 10.0),  # exactly one edge length -> faces meet, no overlap volume
    }
    box = GeometryNode(kind="box", params={"size_x": "sx", "size_y": "sy", "size_z": "sz"})
    shifted = GeometryNode(kind="translate", params={"x": "dx", "y": "sx", "z": "sx"},
                           children=[box])
    # y/z translate are 10 too (params reuse sx=10), so it's a corner-touch -> disjoint.
    assert br.interferes(box, shifted, quant) is False
    # and a box with itself genuinely overlaps
    assert br.interferes(box, box, quant) is True


def test_print_ready_stl_has_facets_and_single_block():
    bored, _box, quant = _bored_box()
    stl = br.to_stl(bored, quant, name="bored", tolerance=0.2)
    assert stl.startswith("solid genesis_bored")
    assert stl.rstrip().endswith("endsolid genesis_bored")
    assert stl.count("facet normal") > 50  # a bored cube tessellates to many facets
    # exactly one body: one opening "solid " line and one "endsolid " line
    assert sum(1 for ln in stl.splitlines() if ln.startswith("solid genesis_bored")) == 1
    assert sum(1 for ln in stl.splitlines() if ln.startswith("endsolid genesis_bored")) == 1


def test_step_export_is_real_iso10303():
    bored, _box, quant = _bored_box()
    step = br.to_step(bored, quant)
    assert step.lstrip().startswith("ISO-10303")
    assert "ENDSEC" in step and "END-ISO-10303" in step
    assert len(step) > 1000


def test_brep_public_api_routes_through_bridge_and_matches_analytic():
    """brep.exact_volume delegates to the bridge here (cadquery not in-process) and
    agrees with the independent analytic geometry.volume_of on a primitive."""
    import gen.brep as brep
    from gen.verification.geometry import volume_of

    _bored, box, quant = _bored_box()
    assert brep._in_process_cadquery() is False  # noqa: SLF001 - asserting the path
    analytic = volume_of(box, quant).value
    exact = brep.exact_volume(box, quant)
    assert math.isclose(analytic, exact, rel_tol=1e-9)


# --- Negative tests: fail LOUD, never a fabricated number --------------------

def test_missing_interpreter_raises_loud(monkeypatch):
    """Pointing the bridge at a nonexistent interpreter raises GeometryError, not a
    silent / guessed geometry."""
    monkeypatch.setenv("GENESIS_CAD_PYTHON", "/nonexistent/python-xyz")
    _bored, box, quant = _bored_box()
    with pytest.raises(GeometryError, match="isolated CadQuery venv"):
        br.exact_volume(box, quant)


def test_malformed_csg_surfaces_worker_error():
    """A CSG referencing an unknown quantity makes the worker fail; the bridge
    re-raises it as a loud GeometryError (no silent default)."""
    box = GeometryNode(kind="box", params={"size_x": "missing", "size_y": "missing",
                                           "size_z": "missing"})
    with pytest.raises(GeometryError):
        br.exact_volume(box, {})  # empty values -> KeyError in the worker


def test_unknown_kind_surfaces_worker_error():
    bad = GeometryNode(kind="dodecahedron", params={}, children=[])
    with pytest.raises(GeometryError, match="failed"):
        br.exact_volume(bad, {})
