"""Tests für Wirtschafts-/Produkt-Pipeline first stone (PLAN §4).

2 Tests:
- Jetpack path: prototype/low-volume costs, experimental market gated by Regulatorik, high repair, scaling only post-cert. Naht to Fertigungs/Realisierungspaket/Techniker/Regulatorik.
- Generic: honest gaps.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.wirtschaft import map_to_wirtschaft_spec, WirtschaftSpec


def test_wirtschaft_jetpack_produces_costs_and_regulatorik_gate():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="wirt-jet-001")
    ing = map_to_ingenieur_spec(concept, run_id="wirt-jet-001")
    spec = map_to_wirtschaft_spec(concept, ing, run_id="wirt-jet-001")

    assert isinstance(spec, WirtschaftSpec)
    assert spec.source_idea == idee
    assert "EUR" in spec.kosten.prototype or "FDM" in spec.kosten.prototype
    assert "high" in spec.kosten.repair_cost.lower()

    assert "experimental" in spec.markt.zielgruppe.lower() or "hobby" in spec.markt.zielgruppe.lower()
    assert "Regulatorik" in spec.markt.skalierung or "certification" in spec.markt.skalierung.lower()
    assert "tether" in spec.reparatur_modell.lower()

    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    assert "Jetpack" in spec.zusammenfassung or "tether" in spec.zusammenfassung.lower()


def test_wirtschaft_no_fabricated_prior_attribution():
    """Schritt-9-Review #9: ``ingenieur`` wird NIE gelesen — Kosten-/Markt-quellen und die
    Kosten-Texte dürfen keinen Konsum von Fertigungs/Realisierungspaket/Techniker/Regulatorik
    behaupten (die 8-25-EUR-Zahl ist eine Kanon-Annahme, keine cost_model-Ableitung)."""
    idee = "Ich will ein Jetpack bauen."
    concept = map_to_system_concept(idee, run_id="wirt-honest-001")
    ing = map_to_ingenieur_spec(concept, run_id="wirt-honest-001")
    spec = map_to_wirtschaft_spec(concept, ing, run_id="wirt-honest-001")

    quellen = [spec.quelle or "", spec.kosten.quelle or "", spec.markt.quelle or ""]
    for tok in ("fertigungs", "realisierungspaket", "techniker", "regulatorik + ", "lern"):
        assert not any(tok in q.lower() for q in quellen), f"fabrizierte Herkunft: {tok}"
    # Konsum-Behauptungen in den Texten selbst
    assert "from Fertigungs" not in spec.kosten.prototype
    assert "per Techniker" not in spec.kosten.repair_cost
    assert "Techniker model" not in spec.reparatur_modell
    assert "kein Prior konsumiert" in (spec.quelle or "")
    assert "Kanon-Annahme" in spec.zusammenfassung


def test_wirtschaft_generic_fallback_honest_gaps():
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="wirt-gen-001")
    ing = map_to_ingenieur_spec(concept, run_id="wirt-gen-001")
    spec = map_to_wirtschaft_spec(concept, ing, run_id="wirt-gen-001")

    assert "TBD" in spec.kosten.prototype or "Lücke" in spec.kosten.quelle
    assert "Lücke" in spec.zusammenfassung or "Generic" in spec.zusammenfassung
    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")