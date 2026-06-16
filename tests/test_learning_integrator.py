"""Tests für learning_integrator (zwölfter / letzter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3 Tabelle + §3.8 (8-Schritt Lern- und Verbesserungsmaschine).
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.boundary_reviser import RevisedFrontMap
from gen.grenzverschiebung.safety_ladder import build_safety_ladder
from gen.grenzverschiebung.learning_integrator import (
    apply_learning_cycle,
)


def test_jetpack_produces_rich_learning_delta_with_rules_failures_and_vorschlaege():
    """Für das Jetpack-Beispiel wendet der Integrator den 8-Schritt-Prozess an und produziert reiches Delta (Rules + Failures + Vorschläge)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="learn-test-001")
    revised = RevisedFrontMap(
        source_traum=front.traum,
        revised_map=front,
        revisions=[],
        zusammenfassung="test revised for learning",
        run_id="learn-test-001",
        quelle="test",
    )
    safety = build_safety_ladder(revised, run_id="learn-test-001")
    delta = apply_learning_cycle(safety=safety, revised=revised, run_id="learn-test-001")

    assert delta.source_traum == idee
    assert len(delta.rules) >= 2
    assert len(delta.failure_modes) >= 1
    assert len(delta.naechste_verbesserungsvorschlaege) >= 2
    # 8-Schritt Referenz in Quelle / Zusammenfassung
    assert "8-Schritt" in delta.zusammenfassung or "§3.8" in (delta.quelle or "")
    # Konkrete Jetpack-Erkenntnisse (Solid-State Shift, Recovery Gate)
    assert any("Solid-State" in r.regel for r in delta.rules)
    assert any("Recovery" in (f.modus + f.evidenz) for f in delta.failure_modes)
    assert delta.quelle is not None


def test_generic_idea_produces_minimal_learning_delta():
    """Generische Idee → minimales Delta (eine Rule, leere Failures, Vorschlag für volle Analyse)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    revised = RevisedFrontMap(
        source_traum=front.traum,
        revised_map=front,
        revisions=[],
        zusammenfassung="test generic",
        run_id="learn-generic",
        quelle="test",
    )
    safety = build_safety_ladder(revised)
    delta = apply_learning_cycle(safety=safety, revised=revised)

    assert len(delta.rules) >= 1
    assert "minimal" in delta.zusammenfassung.lower() or len(delta.failure_modes) == 0
    assert len(delta.naechste_verbesserungsvorschlaege) >= 1
