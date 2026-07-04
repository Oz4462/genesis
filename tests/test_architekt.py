"""Tests für den ersten Architekt-Pipeline Stein.

Siehe GENESIS_PLATFORM_PLAN.md §4.1.
"""

from gen.pipelines.architekt import map_to_system_concept


def test_jetpack_idea_produces_rich_system_concept_with_naht_to_cad():
    """Jetpack-Idee → reiches SystemConcept mit Anforderungen, Baugruppen, Varianten aus Safety-Ladder, offenen Entscheidungen."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="arch-test-001")

    assert concept.source_idea == idee
    assert len(concept.requirements) >= 3
    assert len(concept.main_assemblies) >= 4
    assert len(concept.variants) >= 5
    assert len(concept.open_decisions) >= 1
    # Struktur bleibt; Ehrlichkeit statt Schein-Naht (Schritt 9, #11):
    # map_to_system_concept konsumiert nur den Ideen-String — keinen Grenz-/CAD-Prior.
    assert any("CAD" in a.purpose or "tether" in a.purpose.lower() or "Recovery" in a.purpose for a in concept.main_assemblies)
    assert "kein Prior konsumiert" in (concept.quelle or "")
    assert concept.run_id == "arch-test-001"


def test_architekt_no_fabricated_prior_attribution():
    """Schritt-9-Review #11 (quelle-Überklaim): die Funktion nimmt nur die Idee entgegen;
    quelle-Felder dürfen keinen Konsum von safety_ladder/learning_integrator/boundary_reviser/
    prototype_cad_builder/breakthrough behaupten."""
    concept = map_to_system_concept("Ich will ein Jetpack bauen.", run_id="arch-honest-001")
    quellen = (
        [concept.quelle or ""]
        + [r.quelle or "" for r in concept.requirements]
        + [a.quelle or "" for a in concept.main_assemblies]
    )
    for tok in ("safety_ladder", "learning_integrator", "boundary_reviser", "prototype_cad_builder", "breakthrough", "technology_roadmap"):
        assert not any(tok in q.lower() for q in quellen), f"fabrizierte Herkunft: {tok}"
    # auch Anforderungs-Texte dürfen keine abgeleitete Herkunft behaupten
    assert not any("breakthrough" in r.text.lower() for r in concept.requirements)
    assert "kein Prior konsumiert" in (concept.quelle or "")


def test_generic_idea_produces_minimal_system_concept():
    """Generische Idee → minimales Konzept mit klarer Markierung offener Punkte."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    concept = map_to_system_concept(idee)

    assert len(concept.requirements) >= 1
    assert len(concept.main_assemblies) >= 1
    assert "minimal" in concept.zusammenfassung.lower() or len(concept.open_decisions) >= 1
