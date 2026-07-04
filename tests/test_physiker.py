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
    assert any("Energie" in d.name or "Kräfte" in d.name for d in phys.relevante_domaenen)
    # Ehrlichkeit statt Schein-Naht (Schritt 9, #1): kein Prior wird konsumiert,
    # und die quelle sagt das explizit.
    assert "kein Prior konsumiert" in (phys.quelle or "")
    assert phys.run_id == "phys-test-001"


def _alle_quellen(phys) -> list[str]:
    return (
        [phys.quelle or ""]
        + [d.quelle or "" for d in phys.relevante_domaenen]
        + [g.quelle or "" for g in phys.modell_gleichungen]
        + [b.quelle_ref or "" for b in phys.unsicherheits_budget]
        + [f.quelle or "" for f in phys.falsifikations_plan]
    )


def test_physiker_no_fabricated_prior_attribution():
    """Schritt-9-Review #1: der ``ingenieur``-Parameter wird NIE gelesen; quelle/quelle_ref
    dürfen keinen Konsum von breakthrough/ingenieur/safety_ladder/gren/CAD behaupten.
    Ehrliches Label ist die PLAN-§4.3-Kanon-Vorlage mit deklarierter Lücke."""
    concept = map_to_system_concept("Ich will ein Jetpack bauen.", run_id="phys-honest-001")
    ingen = map_to_ingenieur_spec(concept, run_id="phys-honest-001")
    phys = map_to_physiker_spec(concept, ingen, run_id="phys-honest-001")

    for tok in ("breakthrough", "ingenieur", "safety_ladder", "learning_integrator", "gren ", "lab data"):
        assert not any(tok in q.lower() for q in _alle_quellen(phys)), f"fabrizierte Herkunft: {tok}"
    assert "kein Prior konsumiert" in (phys.quelle or "")
    # Der Jetpack-Pfad deklariert seine Werte als Kanon-Annahmen, nicht als abgeleitete Naht.
    assert "Kanon-Annahme" in phys.zusammenfassung
    assert "aus keinem Prior abgeleitet" in phys.zusammenfassung


def test_generic_produces_minimal_physiker_spec():
    """Generische Idee → minimales PhysikerSpec (Fallback)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    concept = map_to_system_concept(idee)
    ingen = map_to_ingenieur_spec(concept)
    phys = map_to_physiker_spec(concept, ingen)

    assert len(phys.relevante_domaenen) >= 1
    assert len(phys.modell_gleichungen) >= 1
    assert "minimal" in phys.zusammenfassung.lower() or len(phys.falsifikations_plan) >= 1
