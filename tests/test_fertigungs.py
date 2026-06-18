"""Tests für Fertigungs-Pipeline first stone (PLAN §4.7).

2 Tests:
- Jetpack path: concrete Prozesse (FDM primary from DFM + real STL), Kosten, QA, Naht zu advanced DFM/CAD.
- Generic: ehrliche Lücken (Kosten etc.).
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.fertigungs import map_to_fertigungs_spec, FertigungsSpec
from gen.cad.cost_model import estimate_fdm_cost


def test_fertigungs_jetpack_consumes_real_cost_estimate_no_fabricated_band():
    """The Jetpack path must consume the REAL ranged cost estimate from the advanced
    DFM report (cost_model.py, Stein 4) — never the old fabricated "8-25 EUR" prose."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="fertig-jet-001")
    ing = map_to_ingenieur_spec(concept, run_id="fertig-jet-001")
    # The advanced DFM stone computes a real ranged cost; the pipeline must consume it.
    real_hint = estimate_fdm_cost(49.0, "PLA").summary()
    dfm_report = {"overall_printable": True,
                  "processes": [{"process": "FDM", "printable": True, "cost_hint": real_hint}]}
    spec = map_to_fertigungs_spec(concept, ing, dfm_report=dfm_report, run_id="fertig-jet-001")

    assert isinstance(spec, FertigungsSpec)
    assert spec.source_idea == idee
    assert len(spec.gewaehlte_prozesse) >= 1
    fdm = next((p for p in spec.gewaehlte_prozesse if p.name == "FDM"), None)
    assert fdm is not None
    assert "real STL" in (fdm.begruendung or "") or "DFM" in (fdm.begruendung or "").lower() or "real STL" in (fdm.quelle or "") or "DFM" in (fdm.quelle or "").lower()
    assert fdm.datei_stub and "gcode" in fdm.datei_stub.lower()

    assert "FDM" in spec.dfm_report_ref or "advanced" in (spec.dfm_report_ref or "").lower()
    # the REAL estimate is consumed verbatim, and the fabricated band is gone
    assert spec.kosten_modell.gesamt_est == real_hint
    assert "8-25 EUR" not in spec.kosten_modell.gesamt_est
    assert "cost_model" in (spec.kosten_modell.quelle or "")
    assert len(spec.qa_plan.schritte) >= 1

    assert "§4.7" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    assert "Jetpack" in spec.zusammenfassung or "Tether" in spec.zusammenfassung


def test_fertigungs_jetpack_without_cost_model_declares_honest_gap():
    """No cost-bearing DFM report → an honest gap, NEVER a fabricated cost number."""
    idee = "Jetpack für freien Flug über einer Menschenmenge."
    concept = map_to_system_concept(idee, run_id="fertig-jet-002")
    ing = map_to_ingenieur_spec(concept, run_id="fertig-jet-002")
    # a DFM report that carries NO FDM cost (the seam must not invent one)
    spec = map_to_fertigungs_spec(concept, ing, dfm_report={"processes": []}, run_id="fertig-jet-002")
    assert "Lücke" in spec.kosten_modell.gesamt_est
    assert "8-25 EUR" not in spec.kosten_modell.gesamt_est
    assert "€" not in spec.kosten_modell.gesamt_est


def test_fertigungs_generic_fallback_honest_gaps():
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="fertig-gen-001")
    ing = map_to_ingenieur_spec(concept, run_id="fertig-gen-001")
    spec = map_to_fertigungs_spec(concept, ing, run_id="fertig-gen-001")

    assert len(spec.gewaehlte_prozesse) >= 1
    assert "Lücke" in spec.zusammenfassung or "Generic" in spec.zusammenfassung
    assert "TBD" in spec.kosten_modell.gesamt_est or "Lücke" in spec.kosten_modell.quelle
    assert "§4.7" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")