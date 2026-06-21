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
    assert "high" in spec.kosten.repair_cost.lower() or "Techniker" in spec.kosten.quelle or "Realisierungspaket" in spec.kosten.quelle

    assert "experimental" in spec.markt.zielgruppe.lower() or "hobby" in spec.markt.zielgruppe.lower()
    assert "Regulatorik" in spec.markt.skalierung or "certification" in spec.markt.skalierung.lower()
    assert "tether" in spec.reparatur_modell.lower() or "Techniker" in spec.reparatur_modell

    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")
    assert "Jetpack" in spec.zusammenfassung or "tether" in spec.zusammenfassung.lower()


def test_wirtschaft_generic_fallback_honest_gaps():
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="wirt-gen-001")
    ing = map_to_ingenieur_spec(concept, run_id="wirt-gen-001")
    spec = map_to_wirtschaft_spec(concept, ing, run_id="wirt-gen-001")

    assert "TBD" in spec.kosten.prototype or "Lücke" in spec.kosten.quelle
    assert "Lücke" in spec.zusammenfassung or "Generic" in spec.zusammenfassung
    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")