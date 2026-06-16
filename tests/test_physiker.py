"""Tests für physiker (dritter Stein der Fach-Pipelines).

Siehe GENESIS_PLATFORM_PLAN.md §4.3.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.physiker import map_to_physiker_spec


def test_jetpack_produces_rich_physiker_spec_with_naht():
    """Jetpack-Idee → Architekt + Ingenieur → reiches PhysikerSpec mit Domänen, Gleichungen, Budget, Falsifikation (Naht zu prior Stones + CAD/Manufacturing)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="phys-test-001")
    ingen = map_to_ingenieur_spec(concept, run_id="phys-test-001")
    phys = map_to_physiker_spec(concept, ingen, run_id="phys-test-001")

    assert phys.source_idea == idee
    assert len(phys.relevante_domaenen) >= 3
    assert len(phys.modell_gleichungen) >= 2
    assert len(phys.unsicherheits_budget) >= 2
    assert len(phys.falsifikations_plan) >= 2
    # Naht
    assert any("Energie" in d.name or "Kräfte" in d.name for d in phys.relevante_domaenen)
    assert "ingenieur" in (phys.quelle or "").lower() or "architekt" in (phys.quelle or "").lower()
    assert "breakthrough" in (phys.quelle or "").lower() or "gren" in (phys.quelle or "").lower()
    assert phys.run_id == "phys-test-001"


def test_generic_produces_minimal_physiker_spec():
    """Generische Idee → minimales PhysikerSpec (Fallback)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    concept = map_to_system_concept(idee)
    ingen = map_to_ingenieur_spec(concept)
    phys = map_to_physiker_spec(concept, ingen)

    assert len(phys.relevante_domaenen) >= 1
    assert len(phys.modell_gleichungen) >= 1
    assert "minimal" in phys.zusammenfassung.lower() or len(phys.falsifikations_plan) >= 1
