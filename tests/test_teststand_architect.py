"""Tests für teststand_architect (fünfter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.capability_gap_analyzer import analyze_capability_gaps
from gen.grenzverschiebung.milestone_builder import build_milestone_ladder
from gen.grenzverschiebung.teststand_architect import build_test_stand


def test_jetpack_produces_safe_test_stands():
    """Für das Jetpack-Beispiel erzeugt der Architect sichere Prüfstand-Specs zu den Meilensteinen."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="stand-test-001")
    gaps = analyze_capability_gaps(front, run_id="stand-test-001")
    ladder = build_milestone_ladder(front, gaps, run_id="stand-test-001")
    plan = build_test_stand(ladder, run_id="stand-test-001")

    assert plan.source_traum == idee
    assert len(plan.stands) >= 2
    # Jeder Stand hat Sicherheitsmassnahmen + klare Messungen (sicher + testbar)
    for stand in plan.stands:
        assert stand.sicherheitsmassnahmen
        assert stand.messungen
        assert "Tethered" in stand.name or "Energy" in stand.name or "Public" in stand.name or "Frontier" in stand.name


def test_generic_idea_produces_minimal_test_stand():
    """Generische Idee → minimaler Prüfstand (T0 = Mapping Validation)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    gaps = analyze_capability_gaps(idee=idee)
    ladder = build_milestone_ladder(front, gaps)
    plan = build_test_stand(ladder)

    assert len(plan.stands) >= 1
    assert "Frontier Mapping" in plan.stands[0].name or "T0" in plan.stands[0].name
