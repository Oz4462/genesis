"""Characterization test for learning_integrator.apply_learning_cycle.

Facade-detector for the generic (non-jetpack) branch: proves the generic path
genuinely DERIVES its LearningDelta from the real SafetyStagePlan / RevisedFrontMap
input (two different inputs → different output), honestly abstains when the input
carries no actionable signal, and fails loud (ValueError) when both inputs are None.
The rich jetpack branch is protected as a regression.

Siehe GENESIS_PLATFORM_PLAN.md §3.3 + §3.8 (8-Schritt Lern- und Verbesserungsmaschine).
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from gen.grenzverschiebung.development_front import map_development_front
from gen.grenzverschiebung.boundary_reviser import BoundaryRevision, RevisedFrontMap
from gen.grenzverschiebung.safety_ladder import (
    SafetyStage,
    SafetyStagePlan,
    build_safety_ladder,
)
from gen.grenzverschiebung.learning_integrator import apply_learning_cycle


# A traum that hits NEITHER jetpack trigger ("jetpack", "mensch"+"fliegen").
GENERIC_TRAUM_A = "Ein generisches Gerät zur Wasseraufbereitung im Feld."
GENERIC_TRAUM_B = "Eine modulare Solaranlage für netzferne Regionen."


def _stage(name: str, gate: str, messkriterien: list[str], abbruch: list[str]) -> SafetyStage:
    return SafetyStage(
        name=name,
        beschreibung=f"Beschreibung {name}",
        safe_form="Modell, Simulation",
        gate=gate,
        messkriterien=messkriterien,
        abbruch=abbruch,
        quelle="test-safety",
    )


def _plan(traum: str, stages: list[SafetyStage]) -> SafetyStagePlan:
    return SafetyStagePlan(
        source_traum=traum,
        stages=stages,
        zusammenfassung=f"Plan für {traum}",
        run_id="char-run",
        quelle="test-safety-plan",
    )


# --------------------------------------------------------------------------- #
# Facade-detector: two DIFFERENT non-jetpack inputs must produce DIFFERENT output.
# --------------------------------------------------------------------------- #
def test_two_different_safety_plans_yield_different_deltas():
    """If the input were ignored (old facade) both deltas would be identical."""
    plan_a = _plan(GENERIC_TRAUM_A, [_stage("A0 — Sim", "Coverage A", ["m-a1"], ["Gap A"])])
    plan_b = _plan(
        GENERIC_TRAUM_B,
        [
            _stage("B0 — Sim", "Coverage B", ["m-b1"], ["Gap B0"]),
            _stage("B1 — Bench", "Bench B", ["m-b2", "m-b3"], ["Gap B1a", "Gap B1b"]),
        ],
    )

    delta_a = apply_learning_cycle(safety=plan_a)
    delta_b = apply_learning_cycle(safety=plan_b)

    # The output is genuinely consumed: rule texts and counts differ.
    assert [r.regel for r in delta_a.rules] != [r.regel for r in delta_b.rules]
    assert len(delta_a.rules) == 1
    assert len(delta_b.rules) == 2
    assert delta_a.source_traum == GENERIC_TRAUM_A
    assert delta_b.source_traum == GENERIC_TRAUM_B


def test_generic_derives_one_rule_per_stage_and_failure_per_abbruch():
    """Each SafetyStage → exactly one LearningRule; each abbruch criterion → one FailureMode."""
    plan = _plan(
        GENERIC_TRAUM_A,
        [
            _stage("S0 — Sim", "Gate-0", ["mk-0"], ["Abbruch-0a", "Abbruch-0b"]),
            _stage("S1 — Bench", "Gate-1", ["mk-1"], ["Abbruch-1"]),
        ],
    )
    delta = apply_learning_cycle(safety=plan)

    assert len(delta.rules) == 2
    assert len(delta.failure_modes) == 3  # 2 + 1 abbruch criteria

    # Provenance: the stage's name/gate is referenced in the derived artefacts.
    assert any("S0 — Sim" in r.regel and "Gate-0" in r.regel for r in delta.rules)
    assert {f.modus for f in delta.failure_modes} == {"Abbruch-0a", "Abbruch-0b", "Abbruch-1"}
    assert any(f.aus_stufe == "S1 — Bench" for f in delta.failure_modes)
    # Knowledge entry summarises the real plan.
    assert len(delta.wissens_eintraege) == 1
    assert "2 Stufen" in delta.wissens_eintraege[0].titel
    assert "minimal" in delta.zusammenfassung.lower()


def test_both_none_raises_valueerror():
    """No safety AND no revised → fail loud instead of fabricating 'unbekannt' content."""
    with pytest.raises(ValueError, match="mindestens"):
        apply_learning_cycle()


def test_safety_without_stages_and_no_revised_honest_abstention():
    """Input present but no actionable signal → empty rules + explicit LÜCKE marker."""
    empty_plan = _plan(GENERIC_TRAUM_A, [])
    delta = apply_learning_cycle(safety=empty_plan)

    assert delta.rules == []
    assert delta.failure_modes == []
    assert any("LÜCKE" in v for v in delta.naechste_verbesserungsvorschlaege)
    assert "lücke" in delta.zusammenfassung.lower()


def test_only_revised_derives_from_revisions():
    """When only revised is supplied, rules are derived from its BoundaryRevisions."""
    front = map_development_front(GENERIC_TRAUM_A)
    revised = RevisedFrontMap(
        source_traum=front.traum,
        revised_map=front,
        revisions=[
            BoundaryRevision(
                changed_boundary="portable Energie",
                old_typ="needs_breakthrough",
                new_typ="possible_but_unsafe_directly",
                reason="Neue Tech-Evidenz.",
                quelle="boundary_reviser-test",
            ),
        ],
        zusammenfassung="revised generic",
        run_id="char-run",
        quelle="test",
    )
    delta = apply_learning_cycle(safety=None, revised=revised)

    assert len(delta.rules) == 1
    assert "portable Energie" in delta.rules[0].regel
    assert "needs_breakthrough" in delta.rules[0].regel
    assert delta.rules[0].quelle == "boundary_reviser-test"


def test_only_revised_without_revisions_honest_abstention():
    """revised present but carrying no revisions → honest abstention, not a fabricated rule."""
    front = map_development_front(GENERIC_TRAUM_A)
    revised = RevisedFrontMap(
        source_traum=front.traum,
        revised_map=front,
        revisions=[],
        zusammenfassung="revised generic empty",
        run_id="char-run",
        quelle="test",
    )
    delta = apply_learning_cycle(safety=None, revised=revised)

    assert delta.rules == []
    assert any("LÜCKE" in v for v in delta.naechste_verbesserungsvorschlaege)


def test_jetpack_rich_branch_preserved_as_regression():
    """Protected regression: the rich jetpack branch is unchanged (3 rules incl. Solid-State)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    front = map_development_front(idee, run_id="jp-001")
    revised = RevisedFrontMap(
        source_traum=front.traum,
        revised_map=front,
        revisions=[],
        zusammenfassung="test revised",
        run_id="jp-001",
        quelle="test",
    )
    safety = build_safety_ladder(revised, run_id="jp-001")
    delta = apply_learning_cycle(safety=safety, revised=revised, run_id="jp-001")

    assert len(delta.rules) == 3
    assert any("Solid-State" in r.regel for r in delta.rules)
    assert len(delta.failure_modes) == 2
    assert len(delta.wissens_eintraege) == 2
    assert len(delta.naechste_verbesserungsvorschlaege) == 4
    assert "Jetpack" in delta.zusammenfassung


# --------------------------------------------------------------------------- #
# Property-based invariant: for any non-jetpack plan with N>=1 stages,
# #rules == N and #failure_modes == total abbruch criteria.
# --------------------------------------------------------------------------- #
_text = st.text(min_size=1, max_size=20).filter(lambda s: s.strip() != "")


@given(
    stages=st.lists(
        st.builds(
            lambda name, gate, mk, ab: _stage(name, gate, mk, ab),
            name=_text,
            gate=_text,
            mk=st.lists(_text, max_size=3),
            ab=st.lists(_text, max_size=3),
        ),
        min_size=1,
        max_size=5,
    )
)
def test_property_rule_and_failure_counts_match_input(stages: list[SafetyStage]):
    """Invariant: generic path derives exactly one rule per stage and one failure per abbruch."""
    # Use a fixed generic traum so the jetpack branch is never taken.
    plan = _plan("Eine generische Test-Idee ohne Trigger.", stages)
    delta = apply_learning_cycle(safety=plan)

    assert len(delta.rules) == len(stages)
    assert len(delta.failure_modes) == sum(len(s.abbruch) for s in stages)
