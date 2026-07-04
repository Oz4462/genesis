"""Printability WIRED into the run path — pipeline verdict + CLI + STL gate.

The standalone layers (overhang/bridges/first layer, mesh integrity) compose into
``pipeline.assess_printability`` and surface in the CLI: ``--mode print`` reports
the verdict over the demo specs, and the ``--format stl`` export now REFUSES a
kernel mesh that fails the integrity proof instead of shipping it. Honesty cases
pinned: a geometry-less spec is "no_geometry" (the honest complete answer), a
missing CAD kernel is "unavailable" (never a silent pass), a broken mesh is a
blocker, and a fully-bridgeable ceiling composes to ZERO unsupported overhang
(the bridge refinement actually subtracts, on the same tessellation).

Offline, no LLM. Kernel cases are cadquery-gated.

Run:  pytest tests/test_printability_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import GeometryError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Component,
    GeometryNode,
    Quantity,
    Specification,
    ValueOrigin,
)
from gen.pipeline import assess_printability  # noqa: E402

BROKEN_STL = (
    "solid t\n"
    "  facet normal 0 0 0\n    outer loop\n"
    "      vertex 0 0 0\n      vertex 0 1 0\n      vertex 1 0 0\n"
    "    endloop\n  endfacet\n"
    "  facet normal 0 0 0\n    outer loop\n"
    "      vertex 0 0 0\n      vertex 1 0 0\n      vertex 0 0 1\n"
    "    endloop\n  endfacet\n"
    "endsolid t\n"
)                                                       # open tetrahedron: has holes


def _q(qid, v):
    return Quantity(id=qid, name=qid, value=v, unit="mm",
                    origin=ValueOrigin.DECISION, rationale="x")


def _pocket_spec() -> Specification:
    """20x20x10 block with an 8x16x6 pocket opening downward: the ceiling is a
    fully-bridgeable flat region (all four sides anchored, 8 mm span)."""
    node = GeometryNode(kind="difference", children=[
        GeometryNode(kind="box", params={"size_x": "bx", "size_y": "by", "size_z": "bz"}),
        GeometryNode(kind="translate", params={"x": "zero", "y": "zero", "z": "cdz"},
                     children=[GeometryNode(kind="box",
                                            params={"size_x": "cx", "size_y": "cy",
                                                    "size_z": "cz"})]),
    ])
    qs = [_q(k, v) for k, v in
          {"bx": 20.0, "by": 20.0, "bz": 10.0, "cx": 8.0, "cy": 16.0,
           "cz": 6.0, "zero": 0.0, "cdz": -2.0}.items()]
    return Specification(run_id="pocket", idea="pocket block", quantities=qs,
                         components=[Component(id="c_pocket", name="pocket block",
                                               geometry=node)])


def test_geometry_less_spec_is_no_geometry_not_a_pass():
    from gen.demo import drive_shaft_spec

    p = assess_printability(drive_shaft_spec())
    assert p.status == "no_geometry" and not p.ok
    assert p.components == [] and p.mesh is None


def test_missing_kernel_is_unavailable_never_a_silent_pass(monkeypatch):
    def _no_kernel():
        raise GeometryError("cadquery absent (simulated)")

    import gen.brep
    import gen.orientation
    monkeypatch.setattr(gen.brep, "_require_cadquery", _no_kernel)
    monkeypatch.setattr(gen.orientation, "_require_cadquery", _no_kernel)
    p = assess_printability(_pocket_spec())
    assert p.status == "unavailable" and not p.ok
    assert any("nicht beurteilt" in a for a in p.advisories)


def test_capstone_is_printable_with_elephant_foot_advisory():
    pytest.importorskip("cadquery", reason="kernel printability needs cadquery/OCP")
    from gen.demo import capstone_spec

    p = assess_printability(capstone_spec())
    assert p.ok and p.status == "needs_attention" and p.blockers == []
    assert p.mesh is not None and p.mesh["ok"] and p.mesh["genus"] == 1
    (comp,) = p.components
    assert comp["first_layer"]["plate_contact"]
    assert comp["unsupported_overhang_area"] == 0.0     # vertical hole: no overhang
    assert any("Elephant-Foot" in a for a in p.advisories)


def test_bridgeable_ceiling_composes_to_zero_unsupported_overhang():
    pytest.importorskip("cadquery", reason="kernel printability needs cadquery/OCP")
    p = assess_printability(_pocket_spec())
    (comp,) = p.components
    assert comp["overhang"]["overhang_area"] > 100.0    # the blanket rule flags ~8x16
    assert comp["unsupported_overhang_area"] == 0.0     # ...the bridge layer clears it
    assert p.blockers == [] and p.ok
    assert not any("Stützmaterial" in a for a in p.advisories)


def test_geometry_error_after_found_blockers_keeps_them(monkeypatch):
    # D14/pipeline G3: a GeometryError mid-run used to RESET the verdict to "unavailable"
    # with blockers=[] — discarding blockers already proven. A blocker-bearing part whose
    # mesh export then dies must stay "not_printable" with the blockers intact.
    import gen.export.brep_stl as brep_stl
    import gen.orientation

    monkeypatch.setattr(gen.orientation, "overhang_check",
                        lambda geo, qs: {"overhang_area": 0.0})
    monkeypatch.setattr(gen.orientation, "bridge_spans",
                        lambda geo, qs: {"regions": [], "needs_support": True,
                                         "worst_span": 42.0})
    monkeypatch.setattr(gen.orientation, "first_layer_report",
                        lambda geo, qs: {"plate_contact": False,
                                         "elephant_foot_risk": False})

    def _dies(spec):
        raise GeometryError("kernel died during STL export (simulated)")

    monkeypatch.setattr(brep_stl, "specification_to_brep_stl", _dies)
    p = assess_printability(_pocket_spec())
    assert p.status == "not_printable" and not p.ok
    assert len(p.blockers) == 2                          # plate contact + bridge span kept
    assert any("Druckbett-Kontaktfläche" in b for b in p.blockers)
    assert any("Stützmaterial" in b for b in p.blockers)
    assert any("nicht beurteilt" in a for a in p.advisories)   # the cut-off stays visible
    assert p.mesh is None                                # no fabricated mesh verdict


def test_geometry_error_without_blockers_stays_unavailable(monkeypatch):
    # ...but a blocker-FREE partial run remains the honest "unavailable" (unchanged path).
    import gen.orientation

    def _dies(geo, qs):
        raise GeometryError("kernel absent (simulated)")

    monkeypatch.setattr(gen.orientation, "overhang_check", _dies)
    p = assess_printability(_pocket_spec())
    assert p.status == "unavailable" and not p.ok and p.blockers == []


def test_broken_kernel_mesh_is_a_blocker(monkeypatch):
    pytest.importorskip("cadquery", reason="kernel printability needs cadquery/OCP")
    import gen.export.brep_stl as brep_stl
    monkeypatch.setattr(brep_stl, "specification_to_brep_stl", lambda spec: BROKEN_STL)
    p = assess_printability(_pocket_spec())
    assert p.status == "not_printable" and not p.ok
    assert any("Mesh-Integritätsprüfung" in b for b in p.blockers)


def test_cli_stl_export_refuses_a_broken_mesh(monkeypatch):
    pytest.importorskip("cadquery", reason="kernel STL needs cadquery/OCP")
    import gen.export.brep_stl as brep_stl
    from gen.cli import render_spec
    from gen.demo import capstone_spec

    monkeypatch.setattr(brep_stl, "specification_to_brep_stl", lambda spec: BROKEN_STL)
    out = render_spec(capstone_spec(), "stl")
    assert out.startswith("# STL-Export verweigert")
    assert "open" in out                                # the holes are named


def test_cli_mode_print_reports_the_verdicts(capsys):
    pytest.importorskip("cadquery", reason="kernel printability needs cadquery/OCP")
    from gen.cli import main

    rc = main(["--mode", "print"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Druckbarkeit: capstone" in out and "Status: needs_attention" in out
    assert "genus=1" in out                             # the hole, proven in the mesh
    assert "Druckbarkeit: drive_shaft" in out and "Status: no_geometry" in out
    assert "Elephant-Foot" in out