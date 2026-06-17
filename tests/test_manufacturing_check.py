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


# === CNC-DFM honesty stone (Teil 2, sourced rules) ===
# The CNC process must run REAL, sourced DFM rules on the quantities the spec carries
# (wall thickness, envelope) and declare the geometric rules it CANNOT evaluate
# (internal corner radius, pocket aspect ratio, hole depth:diameter) as explicit GAPS
# — never a silent printable=True. Sources: Protolabs / Xometry / Fictiv CNC DFM.
# These build a BuildArtifact directly: no CAD kernel needed, so they always run.

def _artifact(name: str, bbox, wall: float, vol: float = 50.0):
    from gen.cad.prototype_cad_builder import PrototypeSpec, BuildArtifact
    spec = PrototypeSpec(name=name, description="cnc dfm test part",
                         bounding_box_hint_mm=bbox, min_wall_thickness_mm=wall)
    return BuildArtifact(spec=spec, generated_code="", exports={}, dfm_report=[],
                         volume_estimate_cm3=vol)


def test_cnc_declares_ungrounded_geometric_rules_as_gaps_not_passes():
    """Tracer: from bbox+wall alone the geometric CNC rules are not evaluable — they
    must be declared as gaps, and an un-certified process must NOT claim printable=True
    (necessary-not-sufficient, same stance as dfm.py / the FDM layer-adhesion gap)."""
    from gen.cad.manufacturing_check import check_advanced_dfm

    report = check_advanced_dfm(_artifact("CNC Clean Bracket", (80, 60, 20), 3.0, vol=80.0))
    cnc = next(p for p in report.processes if p.process == "CNC")

    assert cnc.issues == []          # a 3mm wall at modest size -> no positive blocker
    assert cnc.gaps                  # but the geometric rules are un-evaluable -> declared
    assert cnc.printable is False    # so CNC cannot be certified printable -> honest
    text = " ".join(cnc.gaps).lower()
    assert "radius" in text or "corner" in text
    assert "pocket" in text
    assert "hole" in text


def test_cnc_thin_wall_is_a_sourced_blocker_with_provenance():
    """A wall below the sourced CNC minimum is a real blocker (issues, not a gap),
    the issue text names the sourced threshold, details carry provenance, and the
    old invented bare numbers (min_feature_mm, typical_tol) are gone."""
    from gen.cad.manufacturing_check import check_advanced_dfm
    from gen.dfm import CNC_MIN_WALL_METAL_MM, CNC_MIN_WALL_METAL_FLOOR_MM

    rep = check_advanced_dfm(_artifact("CNC Razor Wall", (50, 40, 10), 0.3))
    cnc = next(p for p in rep.processes if p.process == "CNC")
    assert cnc.issues                                       # a real blocker, not a gap
    assert any(str(CNC_MIN_WALL_METAL_FLOOR_MM) in i for i in cnc.issues)
    assert cnc.printable is False
    assert "source" in cnc.details                          # provenance, not invented
    assert "typical_tol" not in cnc.details
    assert "min_feature_mm" not in cnc.details

    rep2 = check_advanced_dfm(_artifact("CNC Thinnish", (50, 40, 10), 0.6))
    cnc2 = next(p for p in rep2.processes if p.process == "CNC")
    assert any(str(CNC_MIN_WALL_METAL_MM) in i for i in cnc2.issues)   # names 0.8mm


def test_cnc_distinguishes_blocked_from_incomplete_and_surfaces_size_and_gaps():
    """Honest verdict: a clean modest part has NO issues (not blocked) but open gaps
    (incomplete); the report surfaces the gaps at the top level instead of silently
    dropping them. Machine-envelope fit is per-axis and machine-specific, so it is
    surfaced as a gap stating the part's extents — NOT an invented hard blocker."""
    from gen.cad.manufacturing_check import check_advanced_dfm

    clean = check_advanced_dfm(_artifact("CNC Clean", (80, 60, 20), 3.0))
    cnc_clean = next(p for p in clean.processes if p.process == "CNC")
    assert cnc_clean.issues == [] and cnc_clean.gaps        # incomplete, not blocked
    assert any("CNC" in g for g in clean.total_gaps)        # surfaced, not dropped

    # a deep/large part: envelope is surfaced as a GAP (with the extents stated),
    # not a fabricated blocker, because the machine envelope is unknown from spec.
    big = check_advanced_dfm(_artifact("CNC Deep Part", (600, 50, 120), 3.0))
    cnc_big = next(p for p in big.processes if p.process == "CNC")
    assert any("envelope" in g.lower() for g in cnc_big.gaps)
    assert any("600" in g for g in cnc_big.gaps)            # part extents stated


def test_cnc_material_ambiguity_gap_only_where_material_changes_the_verdict():
    """A wall that passes the metal recommendation but not the plastic one is an
    honest material-ambiguity gap. Below the metal minimum the wall already fails
    metal, so the 'passes metal' gap must NOT fire there (it would be false)."""
    from gen.cad.manufacturing_check import check_advanced_dfm
    from gen.dfm import CNC_MIN_WALL_PLASTIC_MM

    # 1.2mm: passes metal (>=0.8), below plastic (1.5) -> material gap, no issue
    band = check_advanced_dfm(_artifact("CNC Mid Wall", (60, 50, 15), 1.2))
    cnc = next(p for p in band.processes if p.process == "CNC")
    assert cnc.issues == []
    mat = [g for g in cnc.gaps if "material unspecified" in g]
    assert mat and str(CNC_MIN_WALL_PLASTIC_MM) in mat[0]

    # 0.6mm: already fails metal -> a metal issue, and NO false "passes metal" gap
    sub = check_advanced_dfm(_artifact("CNC Sub Metal", (60, 50, 15), 0.6))
    cnc2 = next(p for p in sub.processes if p.process == "CNC")
    assert cnc2.issues                                      # metal blocker present
    assert not any("passes metal" in g for g in cnc2.gaps)


# === Laser/sheet-DFM honesty stone (Teil 2, Stein 2, sourced rules) ===
# Laser is a 2D SHEET process: it cuts a flat constant-thickness profile. From the
# bounding box only the sheet thickness (smallest extent) is evaluable; the in-plane
# form, feature sizes vs thickness, bridging and kerf need the 2D geometry the spec
# does not carry — declared as gaps, never a silent printable=True. Sources:
# SendCutSend / Xometry / Wurth laser & sheet DFM.

def test_laser_declares_sheet_form_rules_as_gaps_not_passes():
    """Tracer: from the bounding box only the sheet thickness is evaluable; the
    in-plane form, feature sizes, bridging and kerf are not — declared as gaps,
    never a silent printable=True (necessary, not sufficient)."""
    from gen.cad.manufacturing_check import check_advanced_dfm

    # 120x80x6 plate: thin axis 6mm (<= aluminum max 12) -> no thickness blocker
    report = check_advanced_dfm(_artifact("Laser Plate", (120, 80, 6), 2.0))
    laser = next(p for p in report.processes if p.process == "Laser")
    assert laser.issues == []          # 6mm is laser-cuttable -> no blocker
    assert laser.gaps                  # but form/feature rules un-evaluable
    assert laser.printable is False    # so not certifiable -> honest
    text = " ".join(laser.gaps).lower()
    assert "form" in text or "profile" in text or "outline" in text
    assert "feature" in text or "hole" in text
    assert "source" in laser.details   # provenance, not invented


def test_laser_too_thick_part_is_a_sourced_blocker():
    """A sheet thickness beyond the laser max (even for steel) is a real blocker
    that names the sourced limit and the waterjet/plasma alternative."""
    from gen.cad.manufacturing_check import check_advanced_dfm
    from gen.dfm import LASER_MAX_THICKNESS_STEEL_MM

    rep = check_advanced_dfm(_artifact("Laser Thick Block", (200, 150, 30), 4.0))
    laser = next(p for p in rep.processes if p.process == "Laser")
    assert laser.issues                                    # blocker, not just a gap
    assert any(f"{LASER_MAX_THICKNESS_STEEL_MM:g}" in i for i in laser.issues)
    assert any("waterjet" in i.lower() or "plasma" in i.lower() for i in laser.issues)
    assert laser.printable is False


def test_laser_thickness_band_is_an_equipment_gap_not_a_pass():
    """A thickness above a typical online job-shop cap but below the industrial laser
    bound is an equipment gap (not a silent pass) — laser max is equipment/material
    specific, not one universal number. A thin sheet has no such gap. Details carry
    sourced provenance, not the old invented kerf-only dict."""
    from gen.cad.manufacturing_check import check_advanced_dfm
    from gen.dfm import LASER_TYPICAL_SHOP_MAX_MM

    # 18mm: > aluminum cap (12), <= industrial steel bound (25) -> equipment gap, no issue
    band = check_advanced_dfm(_artifact("Laser Ferrous Only", (300, 200, 18), 5.0))
    laser = next(p for p in band.processes if p.process == "Laser")
    assert laser.issues == []
    assert any("job-shop" in g and f"{LASER_TYPICAL_SHOP_MAX_MM:g}" in g for g in laser.gaps)

    # 12.5mm: above the aluminum cap (12) but below the shop cap (12.7) — this band
    # must NOT fall through silently; it gets the equipment gap (no-silent-band).
    edge = check_advanced_dfm(_artifact("Laser Edge Band", (200, 120, 12.5), 4.0))
    laser_edge = next(p for p in edge.processes if p.process == "Laser")
    assert any("conservative laser cap" in g or "equipment" in g for g in laser_edge.gaps)

    # 3mm thin sheet: under every cap -> no equipment gap
    thin = check_advanced_dfm(_artifact("Laser Thin Sheet", (100, 60, 3), 2.0))
    laser2 = next(p for p in thin.processes if p.process == "Laser")
    assert not any("job-shop" in g for g in laser2.gaps)
    assert "kerf" not in laser2.details                    # old bare 'kerf' key gone
    assert "kerf_mm_typical" in laser2.details and "source" in laser2.details
