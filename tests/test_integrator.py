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
    # Schritt-9 #7 (verschärft): die Fertigungs-Naht muss ECHT sein. Vorher wurden
    # SystemConcept/IngenieurSpec ohne Pflichtfelder konstruiert → TypeError bei JEDEM
    # Aufruf, vom breiten except zu [{"note": "fertigungs skipped: ..."}] verschluckt —
    # die Naht war permanent tot, während das Manifest sie behauptete.
    fert = manifest["fertigungs"]
    assert isinstance(fert, list) and len(fert) == len(ideas)
    for eintrag in fert:
        assert "note" not in eintrag, f"Fertigungs-Naht tot: {eintrag}"
        assert eintrag["prozesse"], eintrag
        assert eintrag["kosten"], eintrag
    # der Jetpack-Eintrag trägt den Jetpack-Kanon (FDM primary), der generische den Fallback
    assert "FDM" in fert[0]["prozesse"]

    # Honesty (2026-06-19): the idea/fragment bundle is NOT physics-gated (it has no Specification),
    # and it must SAY so instead of letting "complete" read as validated — pointing to the gated path.
    assert "physics_gate" in manifest
    assert "not run" in manifest["physics_gate"].lower()
    summary = (pkg_path / "SUMMARY.md").read_text(encoding="utf-8")
    assert "Physik-Gate" in summary and "--mode bundle" in summary

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


def test_ingenieur_spec_serialization_dumps_real_data_not_placeholder():
    """Regression (2026-06-18 de-rot): the package's ingenieur_spec.json must carry the REAL
    engineering spec, not the old ``locals().get("ingen")``-bug placeholder. Pure — needs no CAD
    kernel, so it runs everywhere (unlike the full-package tests that import-skip build123d)."""
    from gen.pipelines.integrator import _ingenieur_spec_to_dict
    concept = map_to_system_concept("Ich will ein Jetpack bauen.", run_id="ser-test")
    ingen = map_to_ingenieur_spec(concept, run_id="ser-test")
    d = _ingenieur_spec_to_dict(ingen)
    assert "note" not in d  # NOT the "data not available" placeholder the bug always wrote
    assert set(d) >= {"lastfaelle", "material_hinweise", "toleranzen", "failure_modes",
                      "cad_anforderungen", "pruefplan_hinweise"}
    assert isinstance(d["lastfaelle"], list)
    # the mapping yields a real, non-trivial engineering spec (at least one populated section)
    assert d["lastfaelle"] or d["material_hinweise"] or d["failure_modes"]


def test_full_package_rejects_empty_ideas_instead_of_unbound_crash():
    """Regression (2026-06-19): an empty ideas list left the loop vars c/i unbound → a NameError deep
    in the electronics step. It now fails loud with a clear reason up front."""
    with pytest.raises(ValueError):
        build_full_mini_realization_package([], package_name="x", run_id="empty-test")


def test_elektriker_in_package_receives_real_ingenieur_context(monkeypatch):
    """Schritt-9 #8: die Schleifenvariable ``i`` wurde von den enumerate-Loops auf int
    überschrieben — der Elektriker bekam einen Integer statt IngenieurSpec und
    ``getattr(ingenieur, "quelle", "")`` fiel STILL auf "". Der Packager muss dem
    Elektriker das echte (letzte) Konzept + den echten Ingenieur-Kontext geben."""
    import gen.pipelines.integrator as integ
    from gen.pipelines.architekt import SystemConcept
    from gen.pipelines.ingenieur import IngenieurSpec

    captured = {}
    real = integ.map_to_elektriker_spec

    def spy(concept, ingenieur, *, run_id=None):
        captured["concept"] = concept
        captured["ingenieur"] = ingenieur
        return real(concept, ingenieur, run_id=run_id)

    monkeypatch.setattr(integ, "map_to_elektriker_spec", spy)
    ideas = [
        "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt.",
        "Ein einfaches tragbares Gerät für Tests.",
    ]
    integ.build_full_mini_realization_package(ideas, package_name="Ctx Test", run_id="ctx-test-001")

    assert isinstance(captured.get("concept"), SystemConcept)
    assert isinstance(captured.get("ingenieur"), IngenieurSpec), (
        f"Elektriker bekam {type(captured.get('ingenieur')).__name__} statt IngenieurSpec"
    )
    assert captured["concept"].source_idea == ideas[-1]
    assert captured["ingenieur"].source_concept == ideas[-1]


def test_missing_run_id_yields_unique_package_dirs_no_stale_bleed():
    """Schritt-9 #14: ohne run_id landete JEDER Lauf in out/realization_packages/latest_full —
    alte Artefakte des Vorlaufs blieben liegen und bluteten ins neue Paket. Ohne run_id gibt
    es jetzt einen eindeutigen, klar markierten Verzeichnisnamen pro Lauf."""
    idee = ["Ein einfaches tragbares Gerät für Tests."]
    p1 = build_full_mini_realization_package(idee, package_name="Stale A")
    p2 = build_full_mini_realization_package(idee, package_name="Stale B")
    assert p1 != p2
    assert "latest_full" not in p1 and "latest_full" not in p2
