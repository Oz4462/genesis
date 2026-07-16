"""Residual L4 gap closures: GD&T PDF, waterline CAM, FreeCAD mates, autoroute, diagrams, materials CTE."""

from __future__ import annotations

from pathlib import Path

import pytest

from gen.cad.freecad_export import build_mates_document, write_freecad_export
from gen.cad.gcode import generate_waterline_roughing_gcode, multi_axis_cam_capability, verify_gcode
from gen.cad.kicad import manhattan_autoroute, to_kicad_pcb, verify_kicad_pcb
from gen.core.state import Net, Netlist
from gen.electronics import Component, PlacementHint
from gen.export.gdt import annotate_gdt_frames, iso_2768_m_linear_tol_mm, render_drawing_pdf
from gen.export.step_diagram import render_all_step_diagrams, render_step_png
from gen.export.viewer_3d import build_stl_viewer_html
from gen.materials import cte_per_k, fatigue_basquin_params, material_sim_bundle


def test_iso_2768_and_gdt_pdf(tmp_path: Path):
    assert iso_2768_m_linear_tol_mm(50.0) == 0.3
    pdf = render_drawing_pdf(
        {"top": {"dx": 60.0, "dy": 40.0}, "front": {"dx": 60.0, "dy": 8.0}},
        title="unit",
        run_id="r",
        out_path=tmp_path / "d.pdf",
    )
    assert pdf[:4] == b"%PDF"
    assert (tmp_path / "d.pdf").stat().st_size > 0

    import ezdxf
    from io import StringIO

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((-30, -20), (30, -20))
    buf = StringIO()
    doc.write(buf)
    out = annotate_gdt_frames(buf.getvalue(), dx=60, dy=40)
    assert "GENERAL TOL" in out or "ISO 2768" in out


def test_waterline_roughing_verifies():
    prog = generate_waterline_roughing_gcode(40.0, 30.0, 4.0, z_step_mm=1.0)
    assert prog.operation == "waterline_roughing"
    chk = verify_gcode(prog)
    assert chk.ok, chk.issues
    assert "waterline_roughing" in multi_axis_cam_capability()["ops_available"]


def test_freecad_mates_export(tmp_path: Path):
    doc = build_mates_document(
        [{"label": "A", "pos": [0, 0, 0], "bbox_mm": [10, 10, 5]}],
        [{"kind": "offset", "fixed": "WORLD", "moving": "A", "offset_mm": [0, 0, 0], "gap_mm": 0, "note": ""}],
        name="T",
    )
    paths = write_freecad_export(tmp_path, doc)
    assert Path(paths["json"]).is_file()
    macro = Path(paths["macro"]).read_text()
    assert "FreeCAD" in macro and "Placement" in macro


def test_manhattan_autoroute_segments():
    comps = [
        Component(id="U1", name="a", kind="mcu", v_nom=0, i_max=0, p_max_dissip=0, footprint_mm=(5, 5, 1)),
        Component(id="R1", name="b", kind="resistor", v_nom=0, i_max=0, p_max_dissip=0, footprint_mm=(2, 1, 1)),
    ]
    places = [
        PlacementHint(ref_des="U1", pos_mm=(0, 0, 0), keepout_mm=(8, 8, 2)),
        PlacementHint(ref_des="R1", pos_mm=(20, 10, 0), keepout_mm=(4, 4, 1)),
    ]
    nl = Netlist(pins=[], nets=[Net(name="N1", pins=["U1.1", "R1.1"])])
    tracks = manhattan_autoroute(places, nl)
    assert len(tracks) == 1
    assert len(tracks[0]["points"]) == 3
    text = to_kicad_pcb(places, comps, netlist=nl, autoroute=True)
    assert "(segment" in text
    assert verify_kicad_pcb(text, placements=places).ok


def test_step_diagrams_and_viewer(tmp_path: Path):
    steps = [
        {
            "n": 1,
            "title": "Mount plate",
            "action": "Bolt plate down",
            "torque_nm": 1.5,
            "fastener": "M3",
            "part_name": "Plate",
            "checks": ["ok"],
        }
    ]
    png = render_step_png(steps[0])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    updated = render_all_step_diagrams(steps, tmp_path / "images")
    assert Path(updated[0]["image"]).is_file()
    html = build_stl_viewer_html(["a.stl", "b.stl"], title="t", run_id="r")
    assert "three" in html.lower() and "STLLoader" in html


def test_materials_cte_and_fatigue():
    assert cte_per_k("STEEL") == pytest.approx(12e-6)
    a, b = fatigue_basquin_params("ALUMINUM")
    assert a > 0 and b > 0
    bundle = material_sim_bundle("PLA")
    assert bundle["cte_per_k"] is not None
    assert "source" in bundle
