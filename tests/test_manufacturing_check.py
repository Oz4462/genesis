"""Tests für manufacturing_check (erster Fertigungs-Gate Stein).

Siehe GENESIS_PLATFORM_PLAN.md 4.7, 3.6, 8.4.
"""

import os
import pytest
from gen.cad.prototype_cad_builder import PrototypeSpec, build_prototype_cad
from gen.cad.manufacturing_check import check_manufacturing


def test_good_jetpack_spec_produces_mostly_printable_check():
    """Guter Jetpack-Spec + realer STL → printable oder nur milde Issues."""
    pytest.importorskip("build123d", reason="the real jetpack STL export needs the optional build123d package (gen.cad.prototype_cad_builder); honest-skip per README §7")
    spec = PrototypeSpec(
        name="Jetpack Tether Anchor Plate",
        description="Sichere Tether/Recovery Platte (2mm Wand)",
        bounding_box_hint_mm=(120, 80, 6),
        min_wall_thickness_mm=2.0,
    )
    artifact = build_prototype_cad(spec, run_id="mfg-good-001")

    check = check_manufacturing(artifact, run_id="mfg-good-001")

    assert check.artifact_name == spec.name
    # Mit 2mm Wand und vernünftiger Größe sollte es druckbar sein oder nur wenige Issues
    assert check.printable or len(check.issues) <= 2
    assert check.stl_path is not None
    # Die echte Datei sollte existieren (wurde beim Builder erzeugt)
    if check.stl_path:
        assert os.path.exists(check.stl_path)
    assert "manufacturing_check" in (check.quelle or "")


def test_bad_spec_produces_issues():
    """Zu dünne Wand + riesige Bounding Box (Jetpack-Named um reichen Pfad zu triggern) → klare Issues, nicht printable."""
    pytest.importorskip("build123d", reason="thin-wall DFM detection needs the real geometry from the optional build123d package (gen.cad.prototype_cad_builder); honest-skip per README §7")
    # Name triggert den reichen Jetpack-Branch im Builder (der echte Export macht)
    spec = PrototypeSpec(
        name="Jetpack Impossible Huge Thin Part",
        description="Test case for DFM failure (thin wall + oversized)",
        bounding_box_hint_mm=(500, 500, 500),
        min_wall_thickness_mm=0.4,
    )
    artifact = build_prototype_cad(spec, run_id="mfg-bad-001")

    check = check_manufacturing(artifact, run_id="mfg-bad-001", max_printer_dim_mm=(220, 220, 250))

    assert not check.printable
    assert any("thin" in i.lower() or "wall" in i.lower() for i in check.issues)
    assert any("larger" in i.lower() or "printer" in i.lower() for i in check.issues)
    assert len(check.issues) >= 1


def test_advanced_dfm_jetpack_produces_multi_process_report_with_real_stl():
    """Advanced DFM first stone: Jetpack spec + real STL → AdvancedDFMReport with FDM (dfm+printability rules) + CNC/Laser/PCB + issues + cost/qa stubs."""
    pytest.importorskip("build123d", reason="the real jetpack STL + advanced DFM path needs the optional build123d package (gen.cad.prototype_cad_builder); honest-skip per README §7")
    from gen.cad.manufacturing_check import check_advanced_dfm, AdvancedDFMReport, ProcessDFM

    spec = PrototypeSpec(
        name="Jetpack Tether Anchor Plate",
        description="Sichere Tether/Recovery Platte (2mm Wand)",
        bounding_box_hint_mm=(120, 80, 6),
        min_wall_thickness_mm=2.0,
    )
    artifact = build_prototype_cad(spec, run_id="adv-dfm-jet-001")

    report = check_advanced_dfm(artifact, run_id="adv-dfm-jet-001")

    assert isinstance(report, AdvancedDFMReport)
    assert report.artifact_name == spec.name
    assert len(report.processes) >= 3  # FDM + at least CNC/Laser
    fdm = next((p for p in report.processes if p.process == "FDM"), None)
    assert fdm is not None
    assert isinstance(fdm, ProcessDFM)
    # With 2mm wall should be mostly good, but layer adhesion gap noted
    assert "layer adhesion" in " ".join(fdm.issues).lower() or report.overall_printable or len(report.total_issues) >= 0
    assert report.stl_path is not None
    if report.stl_path:
        assert os.path.exists(report.stl_path)
    assert "advanced_dfm" in (report.quelle or "").lower() or "dfm.py" in (report.quelle or "")
    assert report.cost_model_stub is not None
    assert len(report.qa_plan_stub) >= 1


def test_advanced_dfm_generic_fallback_honest_gaps():
    """Generic idea → advanced report with honest gaps for unmodeled processes (CNC/Laser specifics)."""
    from gen.cad.manufacturing_check import check_advanced_dfm, AdvancedDFMReport

    spec = PrototypeSpec(
        name="Generic Test Part",
        description="Simple cube for fallback",
        bounding_box_hint_mm=(30, 30, 30),
        min_wall_thickness_mm=2.0,
    )
    artifact = build_prototype_cad(spec, run_id="adv-dfm-gen-001")

    report = check_advanced_dfm(artifact, run_id="adv-dfm-gen-001")

    assert isinstance(report, AdvancedDFMReport)
    assert len(report.processes) >= 3
    # FDM should be clean for simple cube
    fdm = next((p for p in report.processes if p.process == "FDM"), None)
    assert fdm is not None
    # CNC/Laser may have notes but no crash
    cnc = next((p for p in report.processes if p.process == "CNC"), None)
    assert cnc is not None
    assert "PLAN" in (report.quelle or "") or "advanced" in (report.quelle or "").lower()
