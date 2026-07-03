"""Tests für experiment_designer (vierter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.capability_gap_analyzer import analyze_capability_gaps
from gen.grenzverschiebung.milestone_builder import build_milestone_ladder
from gen.grenzverschiebung.experiment_designer import design_experiment_plan


def test_jetpack_produces_falsifiable_experiments():
    """Für das Jetpack-Beispiel erzeugt der Designer konkrete, falsifizierbare Experimente zu den Meilensteinen."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="exp-test-001")
    gaps = analyze_capability_gaps(front, run_id="exp-test-001")
    ladder = build_milestone_ladder(front, gaps, run_id="exp-test-001")
    plan = design_experiment_plan(ladder, run_id="exp-test-001")

    assert plan.source_traum == idee
    assert len(plan.experiments) >= 2
    # Jedes Experiment hat Hypothesen + klare Erfolgskriterien (falsifizierbar)
    for exp in plan.experiments:
        assert exp.hypothesen
        assert exp.erfolgskriterien
        assert "Tethered" in exp.name or "Energy" in exp.name or "Public" in exp.name or "Frontier" in exp.name


def test_generic_idea_produces_minimal_experiment():
    """Generische Idee → minimaler Experiment-Plan (E0 = Mapping Validation)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    gaps = analyze_capability_gaps(idee=idee)
    ladder = build_milestone_ladder(front, gaps)
    plan = design_experiment_plan(ladder)

    assert len(plan.experiments) >= 1
    assert "Frontier Mapping" in plan.experiments[0].name or "E0" in plan.experiments[0].name
