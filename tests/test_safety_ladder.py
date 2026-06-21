"""Tests für safety_ladder (elfter Stein der Grenzverschiebungs-Module).

Siehe GENESIS_PLATFORM_PLAN.md §3.3.
"""

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.boundary_reviser import RevisedFrontMap
from gen.grenzverschiebung.safety_ladder import build_safety_ladder


def test_jetpack_produces_6_stage_safety_ladder():
    """Für das Jetpack-Beispiel erzeugt der Ladder die 6-stufige Leiter mit safe forms (Modell bis bemannt public)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="safety-test-001")
    # Minimal valid RevisedFrontMap (safety impl branches nur auf source_traum; prior chain getestet in eigenen Modulen)
    revised = RevisedFrontMap(
        source_traum=front.traum,
        revised_map=front,
        revisions=[],
        zusammenfassung="test revised for safety ladder (jetpack)",
        run_id="safety-test-001",
        quelle="test_safety_ladder",
    )
    plan = build_safety_ladder(revised, run_id="safety-test-001")

    assert plan.source_traum == idee
    assert len(plan.stages) == 6
    safe_forms = [s.safe_form for s in plan.stages]
    assert "Modell, Simulation" in safe_forms[0]
    assert "bemannt, free (mit regulatorischer Freigabe, public demo)" in safe_forms[5]
    # Each stage has gate and messkriterien
    assert all(s.gate and s.messkriterien for s in plan.stages)


def test_generic_idea_produces_minimal_safety_ladder():
    """Generische Idee → minimale Leiter (S0 = Modell/Simulation)."""
    idee = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."
    front = map_development_front(idee)
    revised = RevisedFrontMap(
        source_traum=front.traum,
        revised_map=front,
        revisions=[],
        zusammenfassung="test revised for safety ladder (generic)",
        run_id="safety-test-generic",
        quelle="test_safety_ladder",
    )
    plan = build_safety_ladder(revised)

    assert len(plan.stages) >= 1
    assert "Modell, Simulation" in plan.stages[0].safe_form
