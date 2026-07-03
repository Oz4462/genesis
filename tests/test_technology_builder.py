"""Tests für technology_builder (siebter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.capability_gap_analyzer import analyze_capability_gaps
from gen.grenzverschiebung.milestone_builder import build_milestone_ladder
from gen.grenzverschiebung.teststand_architect import build_test_stand
from gen.grenzverschiebung.technology_roadmapper import build_technology_roadmap
from gen.grenzverschiebung.technology_builder import build_technology_prototype


def test_jetpack_produces_first_prototypes():
    """Für das Jetpack-Beispiel erzeugt der Builder die ersten konkreten Prototyp-Specs aus der Roadmap."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="proto-test-001")
    gaps = analyze_capability_gaps(front, run_id="proto-test-001")
    ladder = build_milestone_ladder(front, gaps, run_id="proto-test-001")
    stand = build_test_stand(ladder, run_id="proto-test-001")
    roadmap = build_technology_roadmap(stand, run_id="proto-test-001")
    plan = build_technology_prototype(roadmap, run_id="proto-test-001")

    assert plan.source_traum == idee
    assert len(plan.prototypes) >= 1
    for p in plan.prototypes:
        assert p.anforderungen
        assert p.test_stand_tie_in
        assert "Energie" in p.name or "Redundant" in p.name or "Recovery" in p.name


def test_generic_idea_produces_minimal_prototype():
    """Generische Idee → minimaler Prototyp (P0)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    gaps = analyze_capability_gaps(idee=idee)
    ladder = build_milestone_ladder(front, gaps)
    stand = build_test_stand(ladder)
    roadmap = build_technology_roadmap(stand)
    plan = build_technology_prototype(roadmap)

    assert len(plan.prototypes) >= 1
    assert "Grundlegender" in plan.prototypes[0].name or "P0" in plan.prototypes[0].name
