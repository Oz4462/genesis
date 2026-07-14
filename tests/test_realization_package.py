"""Phase C: structured BOM / harness / drawings package helpers."""
from __future__ import annotations

from gen.cad.prototype_cad_builder import BuildArtifact, PrototypeSpec
from gen.pipelines.realization_package import (
    assemble_package_bom,
    build_drawings_section,
    build_harness_section,
    build_mechanical_bom_lines,
    write_drawings_section,
    write_harness_section,
    write_package_bom,
)


class _Frag:
    def __init__(self, name: str, idea: str):
        spec = PrototypeSpec(
            name=name,
            description="test part",
            bounding_box_hint_mm=(40, 30, 10),
            min_wall_thickness_mm=2.0,
            material_hint="PLA",
        )
        self.cad_artifact = BuildArtifact(
            spec=spec,
            generated_code="",
            exports={},
            dfm_report=[],
            volume_estimate_cm3=12.0,
        )
        self.source_idea = idea


def test_c5_mechanical_bom_lines_from_fragments():
    frags = [_Frag("Bracket A", "idea-a"), _Frag("Bracket B", "idea-b")]
    lines = build_mechanical_bom_lines(frags)
    assert len(lines) == 2
    assert lines[0].domain == "mechanical"
    assert lines[0].source_idea == "idea-a"
    assert lines[0].material_hint == "PLA"


def test_c5_unified_bom_includes_elec_and_gaps():
    frags = [_Frag("Part", "idea")]
    bom = assemble_package_bom(
        frags,
        [{"id": "R1", "name": "10k resistor", "quantity": 2}],
        run_id="t1",
    )
    assert bom["schema"] == "genesis-bom-v1"
    assert bom["counts"]["mechanical"] == 1
    assert bom["counts"]["electronic"] == 1
    assert bom["counts"]["total"] == 2


def test_c6_harness_section_records_gaps_when_empty():
    sec = build_harness_section({}, run_id="h1")
    assert sec["schema"] == "genesis-harness-v1"
    assert sec["gaps"]
    assert any("harness" in g.lower() for g in sec["gaps"])


def test_c7_drawings_section_sets_drawing_gap(tmp_path):
    frags = [_Frag("Plate", "idea")]

    class _Asm:
        combined_stl = None
        part_files = []

    sec = build_drawings_section(frags, _Asm(), run_id="d1", pkg_name="pkg")
    assert sec["drawing_gap"] is True
    assert sec["parts"]
    p = write_drawings_section(tmp_path, sec)
    assert p.exists()
    assert (tmp_path / "DRAWINGS.md").exists()
    text = (tmp_path / "DRAWINGS.md").read_text()
    assert "drawing_gap" in text.lower() or "Gap" in text


def test_write_package_bom_and_harness(tmp_path):
    frags = [_Frag("X", "y")]
    bom = assemble_package_bom(frags, None, run_id="w")
    write_package_bom(tmp_path, bom)
    assert (tmp_path / "bom.json").exists()
    write_harness_section(tmp_path, build_harness_section(None))
    assert (tmp_path / "harness_package.json").exists()
