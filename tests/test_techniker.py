"""Tests für techniker (vierter Stein der Fach-Pipelines).

Siehe GENESIS_PLATFORM_PLAN.md §4.4.
"""

from gen.pipelines.architekt import map_to_system_concept
from gen.pipelines.ingenieur import map_to_ingenieur_spec
from gen.pipelines.physiker import map_to_physiker_spec
from gen.pipelines.techniker import map_to_techniker_spec


def test_jetpack_produces_realistic_techniker_spec_with_montage_steps():
    """Jetpack-Idee → Architekt + Ingenieur + Physiker → TechnikerSpec mit konkreten Montageschritten für Tether-Anchor (Zugänglichkeit, Werkzeuge, Fehler, Prüfung)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="tech-test-001")
    ingen = map_to_ingenieur_spec(concept, run_id="tech-test-001")
    phys = map_to_physiker_spec(concept, ingen, run_id="tech-test-001")
    tech = map_to_techniker_spec(concept, ingen, phys, run_id="tech-test-001")

    assert tech.source_idea == idee
    assert len(tech.montage_plan) >= 3
    assert len(tech.werkzeug_liste) >= 3
    assert len(tech.pruef_schritte) >= 2
    assert len(tech.wartungs_plan) >= 1
    assert len(tech.reparatur_hinweise) >= 1
    # Naht + Realismus
    assert any("Tether" in s.name or "Recovery" in s.name for s in tech.montage_plan)
    assert any("Bohrmaschine" in w or "Messschieber" in w for w in tech.werkzeug_liste)
    assert "techniker" in (tech.quelle or "").lower() or "physiker" in (tech.quelle or "").lower()
    assert tech.run_id == "tech-test-001"


def test_generic_produces_minimal_techniker_spec():
    """Generische Idee → minimales TechnikerSpec (Fallback)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    concept = map_to_system_concept(idee)
    ingen = map_to_ingenieur_spec(concept)
    phys = map_to_physiker_spec(concept, ingen)
    tech = map_to_techniker_spec(concept, ingen, phys)

    assert len(tech.montage_plan) >= 1
    assert "minimal" in tech.zusammenfassung.lower() or len(tech.werkzeug_liste) >= 1
