"""Tests für Fertigungs-Pipeline first stone (PLAN §4.7).

2 Tests:
- Jetpack path: concrete Prozesse (FDM primary from DFM + real STL), Kosten, QA, Naht zu advanced DFM/CAD.
- Generic: ehrliche Lücken (Kosten etc.).
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.fertigungs import map_to_fertigungs_spec, FertigungsSpec


def test_fertigungs_jetpack_produces_fdm_primary_with_dfm_naht():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="fertig-jet-001")
    ing = map_to_ingenieur_spec(concept, run_id="fertig-jet-001")
    # Simulate DFM report from advanced (as in packager Naht)
    dfm_stub = {"overall_printable": True, "processes": [{"p": "FDM", "printable": True}]}
    spec = map_to_fertigungs_spec(concept, ing, dfm_report=dfm_stub, run_id="fertig-jet-001")

    assert isinstance(spec, FertigungsSpec)
    assert spec.source_idea == idee
    assert len(spec.gewaehlte_prozesse) >= 1
    fdm = next((p for p in spec.gewaehlte_prozesse if p.name == "FDM"), None)
    assert fdm is not None
    assert "real STL" in (fdm.begruendung or "") or "DFM" in (fdm.begruendung or "").lower() or "real STL" in (fdm.quelle or "") or "DFM" in (fdm.quelle or "").lower()
    assert fdm.datei_stub and "gcode" in fdm.datei_stub.lower()

    assert "FDM" in spec.dfm_report_ref or "advanced" in (spec.dfm_report_ref or "").lower()
    assert "EUR" in spec.kosten_modell.gesamt_est or "TBD" in spec.kosten_modell.gesamt_est
    assert len(spec.qa_plan.schritte) >= 1

    assert "§4.7" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    assert "Jetpack" in spec.zusammenfassung or "Tether" in spec.zusammenfassung


def test_fertigungs_generic_fallback_honest_gaps():
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="fertig-gen-001")
    ing = map_to_ingenieur_spec(concept, run_id="fertig-gen-001")
    spec = map_to_fertigungs_spec(concept, ing, run_id="fertig-gen-001")

    assert len(spec.gewaehlte_prozesse) >= 1
    assert "Lücke" in spec.zusammenfassung or "Generic" in spec.zusammenfassung
    assert "TBD" in spec.kosten_modell.gesamt_est or "Lücke" in spec.kosten_modell.quelle
    assert "§4.7" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")