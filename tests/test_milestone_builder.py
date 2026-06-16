"""Tests für milestone_builder (dritter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.capability_gap_analyzer import analyze_capability_gaps
from gen.grenzverschiebung.milestone_builder import build_milestone_ladder


def test_jetpack_produces_ordered_milestone_ladder():
    """Für das Jetpack-Beispiel erzeugt der Builder eine geordnete Leiter mit klaren Meilensteinen."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="ladder-test-001")
    gaps = analyze_capability_gaps(front, run_id="ladder-test-001")
    ladder = build_milestone_ladder(front, gaps, run_id="ladder-test-001")

    assert ladder.source_traum == idee
    assert len(ladder.milestones) >= 3
    # Die Leiter ist geordnet (M0, M1, ...)
    names = [m.name for m in ladder.milestones]
    assert any("M0" in n or "tethered" in n.lower() for n in names)
    assert any("M1" in n or "energy" in n.lower() for n in names)
    # Jeder Meilenstein hat DoD und nächste Aktion
    assert all(m.definition_of_done and m.naechstes_experiment for m in ladder.milestones)


def test_generic_idea_produces_minimal_ladder():
    """Generische Idee → minimale Leiter (M0 = Mapping Complete)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    gaps = analyze_capability_gaps(idee=idee)
    ladder = build_milestone_ladder(front, gaps)

    assert len(ladder.milestones) >= 1
    assert "Frontier Mapping" in ladder.milestones[0].name or "M0" in ladder.milestones[0].name
