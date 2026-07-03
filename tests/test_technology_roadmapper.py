"""Tests für technology_roadmapper (sechster Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.capability_gap_analyzer import analyze_capability_gaps
from gen.grenzverschiebung.milestone_builder import build_milestone_ladder
from gen.grenzverschiebung.teststand_architect import build_test_stand
from gen.grenzverschiebung.technology_roadmapper import build_technology_roadmap


def test_jetpack_produces_technology_roadmap_with_paths():
    """Für das Jetpack-Beispiel erzeugt der Roadmapper konkrete fehlende Techs mit mehreren Pfaden."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="road-test-001")
    gaps = analyze_capability_gaps(front, run_id="road-test-001")
    ladder = build_milestone_ladder(front, gaps, run_id="road-test-001")
    stand = build_test_stand(ladder, run_id="road-test-001")
    roadmap = build_technology_roadmap(stand, run_id="road-test-001")

    assert roadmap.source_traum == idee
    assert len(roadmap.gaps) >= 2
    for g in roadmap.gaps:
        assert g.moegliche_pfade
        assert g.geschaetzter_aufwand
        assert "Energie" in g.name or "Redundant" in g.name or "Recovery" in g.name


def test_generic_idea_produces_minimal_roadmap():
    """Generische Idee → minimale Roadmap (ein Gap mit Pfad)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    gaps = analyze_capability_gaps(idee=idee)
    ladder = build_milestone_ladder(front, gaps)
    stand = build_test_stand(ladder)
    roadmap = build_technology_roadmap(stand)

    assert len(roadmap.gaps) >= 1
    assert "Bewertung" in roadmap.gaps[0].name or "Grundlegend" in roadmap.gaps[0].name
