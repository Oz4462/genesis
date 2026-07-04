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
    # Realismus + Ehrlichkeit statt Schein-Naht (Schritt 9, #2)
    assert any("Tether" in s.name or "Recovery" in s.name for s in tech.montage_plan)
    assert any("Bohrmaschine" in w or "Messschieber" in w for w in tech.werkzeug_liste)
    assert "kein Prior konsumiert" in (tech.quelle or "")
    assert tech.run_id == "tech-test-001"


def test_techniker_no_fabricated_prior_attribution():
    """Schritt-9-Review #2: ``ingenieur`` und ``physiker`` werden NIE gelesen; die
    Montageschritte (quelle + input) dürfen keinen Konsum von physiker/ingenieur/
    manufacturing_check/safety_ladder behaupten. Ehrliches Label: PLAN-§4.4-Kanon-Vorlage."""
    concept = map_to_system_concept("Ich will ein Jetpack bauen.", run_id="tech-honest-001")
    ingen = map_to_ingenieur_spec(concept, run_id="tech-honest-001")
    phys = map_to_physiker_spec(concept, ingen, run_id="tech-honest-001")
    tech = map_to_techniker_spec(concept, ingen, phys, run_id="tech-honest-001")

    felder = [tech.quelle or ""]
    for s in tech.montage_plan:
        felder += [s.quelle or "", s.input]
    for tok in ("physiker", "ingenieur", "manufacturing_check", "safety_ladder"):
        assert not any(tok in f.lower() for f in felder), f"fabrizierte Herkunft: {tok}"
    assert "kein Prior konsumiert" in (tech.quelle or "")
    assert "Kanon-Annahme" in tech.zusammenfassung
    assert "aus keinem Prior abgeleitet" in tech.zusammenfassung


def test_generic_produces_minimal_techniker_spec():
    """Generische Idee → minimales TechnikerSpec (Fallback)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    concept = map_to_system_concept(idee)
    ingen = map_to_ingenieur_spec(concept)
    phys = map_to_physiker_spec(concept, ingen)
    tech = map_to_techniker_spec(concept, ingen, phys)

    assert len(tech.montage_plan) >= 1
    assert "minimal" in tech.zusammenfassung.lower() or len(tech.werkzeug_liste) >= 1
