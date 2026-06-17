"""Tests für den Integrator (Seam-Closer + Realisierungspaket-Fragment).

Siehe GENESIS_PLATFORM_PLAN.md §1 + §3.6 + §4.1/4.2.
"""

import os
import pytest
from pathlib import Path
from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.integrator import build_realization_fragment, build_full_mini_realization_package


def test_jetpack_chain_produces_real_package_with_stl_report_and_specs():
    """Jetpack-Idee → Architekt + Ingenieur → Integrator → reales mini Realisierungspaket mit STL + REPORT + 2 JSONs."""
    pytest.importorskip("build123d", reason="the real >1KB tether_anchor.stl in the package needs the optional build123d package (gen.cad.prototype_cad_builder); honest-skip per README §7")
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="int-test-001")
    ingen = map_to_ingenieur_spec(concept, run_id="int-test-001")
    frag = build_realization_fragment(concept, ingen, focus_assembly_name='Tether / Harness', run_id="int-test-001")

    assert frag.source_idea == idee
    assert frag.cad_artifact is not None
    assert frag.manufacturing_check is not None
    assert frag.manufacturing_check.printable in (True, False)  # je nach Spec

    # Real package dir mit Inhalt
    pkg = Path("out") / "genesis_realization_fragments" / "int-test-001"
    assert pkg.exists()
    files = sorted([p.name for p in pkg.iterdir()])
    assert "tether_anchor.stl" in files
    assert "REPORT.md" in files
    assert "system_concept.json" in files
    assert "ingenieur_spec.json" in files

    stl = pkg / "tether_anchor.stl"
    assert stl.exists()
    assert os.path.getsize(stl) > 1000  # echte Mesh-Datei

    # Naht zu CAD + Gate
    assert "CAD" in frag.zusammenfassung or "real" in frag.zusammenfassung.lower()
    assert "manufacturing" in (frag.quelle or "").lower() or "gate" in (frag.quelle or "").lower()


def test_packager_produces_richer_package_with_bom_and_assembly():
    """Multiple ideas → full mini packager → richer package with bom, costs, testplan, assembly."""
    import json
    ideas = [
        "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt.",
        "Ein einfaches tragbares Gerät für Tests."
    ]
    pkg = build_full_mini_realization_package(ideas, package_name="Test Full Mini", run_id="pack-test-001")
    pkg_path = Path(pkg)
    assert pkg_path.exists()
    files = [p.name for p in pkg_path.iterdir()]
    assert "manifest.json" in files
    assert "SUMMARY.md" in files
    manifest = json.loads((pkg_path / "manifest.json").read_text())
    assert "bom" in manifest
    assert len(manifest["bom"]) >= 1
    assert "costs" in manifest
    assert "test_plan" in manifest
    assert "assembly" in manifest
    # at least the stls from the frags
    stl_files = [f for f in files if f.endswith(".stl")]
    assert len(stl_files) >= 1

    # Realisierungspaket enrichment: drawings + regulatorik stubs + richer manifest
    assert "DRAWINGS.md" in files
    assert "REGULATORIK.md" in files
    assert "advanced_dfm" in manifest
    assert "drawings" in manifest
    assert "regulatorik" in manifest
    assert "open_gaps" in manifest
    assert "fertigungs" in manifest  # Naht from Fertigungs first stone

    drawings = (pkg_path / "DRAWINGS.md").read_text(encoding="utf-8")
    assert "Zeichnungen" in drawings or "drawings" in drawings.lower()
    assert "Gap" in drawings  # honest gap

    reg = (pkg_path / "REGULATORIK.md").read_text(encoding="utf-8")
    assert "Regulatorik" in reg or "regulator" in reg.lower()
    assert "Gap" in reg or "Lücke" in reg
    assert "PLAN" in reg or "safety" in reg.lower()

    # Realisierungspaket complete additions
    assert (pkg_path / "SCHALTPLAN.md").exists()
    assert (pkg_path / "MONTAGEANLEITUNG.md").exists()
    sch = (pkg_path / "SCHALTPLAN.md").read_text(encoding="utf-8")
    assert "Schaltplan" in sch or "48V" in sch
    mon = (pkg_path / "MONTAGEANLEITUNG.md").read_text(encoding="utf-8")
    assert "Montage" in mon or "torque" in mon.lower()
