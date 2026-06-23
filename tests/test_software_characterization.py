"""Characterization tests for the generic branch of ``map_to_software_spec``.

These tests were written to FAIL against the old hollow facade (a fixed
SoftwareSpec — one MainController, one BasicAPI, manual-flash 'No rollback',
one-line testplan — that ignored ``concept`` and ``ingenieur``). They prove:

1. two DIFFERENT non-jetpack inputs yield MEANINGFULLY different output
   (the inputs are genuinely consumed, not a constant stub);
2. a signal-free input (blank idea + no assemblies) raises ValueError
   (honest abstention, no fabricated stub — keine stillen Defaults);
3. the gate intent holds: every EmbeddedComponent lists ≥1 failure state and
   every APISpec has non-empty input/output/sicherheit;
4. update/rollback is an EXPLICIT honest gap, never a silent 'No rollback';
5. the jetpack branch stays byte-stable (protected regression).
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from gen.pipelines.architekt import (
    AssemblyConcept,
    SystemConcept,
    SystemRequirement,
    map_to_system_concept,
)
from gen.pipelines.ingenieur import (
    FailureMode,
    IngenieurSpec,
    map_to_ingenieur_spec,
)
from gen.pipelines.software import map_to_software_spec, SoftwareSpec


def _concept(idea: str, assemblies: list[AssemblyConcept]) -> SystemConcept:
    """Build a SystemConcept directly (real constructor, real fields)."""
    return SystemConcept(
        source_idea=idea,
        requirements=[SystemRequirement("R", "test")],
        main_assemblies=assemblies,
        variants=["v"],
        open_decisions=["d"],
        zusammenfassung="z",
        run_id="char-001",
    )


def _ingenieur(idea: str, failure_modes: list[FailureMode]) -> IngenieurSpec:
    """Build an IngenieurSpec directly with chosen failure modes."""
    return IngenieurSpec(
        source_concept=idea,
        lastfaelle=[],
        material_hinweise=[],
        toleranzen=[],
        failure_modes=failure_modes,
        cad_anforderungen=[],
        pruefplan_hinweise=[],
        zusammenfassung="z",
        run_id="char-001",
    )


# --- Facade-killer: two different inputs → meaningfully different output ----

def test_two_different_inputs_yield_different_specs():
    """The old facade returned the SAME spec for every non-jetpack idea."""
    concept_a = _concept(
        "Solarbetriebener Bewässerungsroboter",
        [AssemblyConcept("Pumpe", "Wasser fördern", ["Power", "Sensor"], "q")],
    )
    ing_a = _ingenieur(
        "Solarbetriebener Bewässerungsroboter",
        [FailureMode("pump_dry_run", "Pumpe", "Trockenlauf", "Drucksensor", "q")],
    )

    concept_b = _concept(
        "Autonomer Lagerlift",
        [AssemblyConcept("Hubmotor", "Last heben", ["Antrieb", "Encoder"], "q")],
    )
    ing_b = _ingenieur(
        "Autonomer Lagerlift",
        [FailureMode("overspeed", "Hubmotor", "Zu schnell", "Encoder", "q")],
    )

    spec_a = map_to_software_spec(concept_a, ing_a)
    spec_b = map_to_software_spec(concept_b, ing_b)

    # Component names, summaries and testplans must all differ.
    assert [e.name for e in spec_a.embedded_components] != [
        e.name for e in spec_b.embedded_components
    ]
    assert spec_a.zusammenfassung != spec_b.zusammenfassung
    assert spec_a.testplan != spec_b.testplan

    # The derived failure modes appear in the right component's failure states.
    assert any("pump_dry_run" in e.fehler_zustaende for e in spec_a.embedded_components)
    assert any("overspeed" in e.fehler_zustaende for e in spec_b.embedded_components)

    # The fault-injection testplan is derived from the actual failure modes.
    assert any("pump_dry_run" in t for t in spec_a.testplan)
    assert any("overspeed" in t for t in spec_b.testplan)


def test_embedded_derived_from_assemblies_and_source_idea():
    """Each control-relevant assembly becomes its own component."""
    concept = _concept(
        "Modulares Pflegebett",
        [
            AssemblyConcept("Liegefläche", "Trägt Patient", ["Mounting"], "q"),  # structural
            AssemblyConcept("Verstellmotor", "Neigung steuern", ["Power", "Steuer"], "q"),
        ],
    )
    ing = _ingenieur("Modulares Pflegebett", [])
    spec = map_to_software_spec(concept, ing)

    names = [e.name for e in spec.embedded_components]
    # Control-relevant assembly drives a component; purely structural one does not.
    assert any("Verstellmotor" in n for n in names)
    assert not any("Liegefläche" in n for n in names)
    assert "Modulares Pflegebett" in spec.zusammenfassung


# --- Gate intent: no unhandled failure state, no API without contract ------

def test_gate_every_component_has_failure_state_and_api_has_contract():
    concept = _concept(
        "Kompaktkühler",
        [AssemblyConcept("Kompressor", "Kühlen", ["Power"], "q")],
    )
    ing = _ingenieur("Kompaktkühler", [])
    spec = map_to_software_spec(concept, ing)

    for comp in spec.embedded_components:
        assert len(comp.fehler_zustaende) >= 1, comp
    for api in spec.apis:
        assert api.input.strip()
        assert api.output.strip()
        assert api.sicherheit.strip()


def test_update_rollback_is_explicit_gap_not_silent_no_rollback():
    """The honest fix declares rollback UNKNOWN, never a flat 'No rollback'."""
    concept = _concept(
        "Tischlüfter",
        [AssemblyConcept("Lüftermotor", "Luft bewegen", ["Power"], "q")],
    )
    spec = map_to_software_spec(concept, _ingenieur("Tischlüfter", []))
    rollback = spec.update_pfad.rollback.lower()
    assert "unbekannt" in rollback or "lücke" in rollback
    # The old facade asserted exactly 'No rollback' as if analysed — must be gone.
    assert spec.update_pfad.rollback != "No rollback (Lücke)"


# --- Honest abstention on a signal-free input ------------------------------

def test_blank_idea_no_assemblies_raises():
    concept = _concept("   ", [])
    with pytest.raises(ValueError):
        map_to_software_spec(concept, _ingenieur("", []))


def test_blank_idea_with_assemblies_still_works():
    """A blank idea is still actionable if assemblies carry signal."""
    concept = _concept(
        "",
        [AssemblyConcept("Steuerung", "Regelt", ["Sensor"], "q")],
    )
    spec = map_to_software_spec(concept, _ingenieur("", []))
    assert len(spec.embedded_components) >= 1


def test_no_control_assembly_falls_back_to_honest_monitor():
    concept = _concept(
        "Statisches Regal",
        [AssemblyConcept("Rahmen", "Trägt Last", ["Mounting"], "q")],
    )
    spec = map_to_software_spec(concept, _ingenieur("Statisches Regal", []))
    assert len(spec.embedded_components) == 1
    assert spec.embedded_components[0].name == "SystemMonitor"
    assert "Lücke" in spec.embedded_components[0].funktion


# --- Protected regression: jetpack branch byte-stable ----------------------

def test_jetpack_branch_unchanged():
    idee = "Ich will ein Jetpack bauen, das Menschen sicher fliegen lässt."
    concept = map_to_system_concept(idee, run_id="jet-001")
    ing = map_to_ingenieur_spec(concept, run_id="jet-001")
    spec = map_to_software_spec(concept, ing, run_id="jet-001")

    assert any("ThrustController" in e.name for e in spec.embedded_components)
    assert any("TetherSafety" in e.name for e in spec.embedded_components)
    assert any("overtemp" in str(e.fehler_zustaende) for e in spec.embedded_components)
    assert any("GroundTelemetry" in a.name for a in spec.apis)
    # NOTE: the jetpack branch is kept byte-stable (out of scope to change). It
    # carries a pre-existing trailing-comma typo that wraps update_pfad in a
    # 1-tuple, so we match via str() exactly as the legacy test does rather than
    # touch that line. Documented in docs/audit/DEPTH_AUDIT_software.md.
    assert "Rollback" in str(spec.update_pfad)
    assert len(spec.testplan) == 4
    assert "Jetpack" in spec.zusammenfassung


# --- Property: any non-blank non-jetpack idea is consumed honestly ---------

@given(
    idea=st.text(min_size=1, max_size=40).filter(
        lambda s: s.strip()
        and "jetpack" not in s.lower()
        and "flug" not in s.lower()
    ),
    fm_name=st.sampled_from(["jam", "stall", "overcurrent", "leak"]),
)
def test_property_idea_consumed_and_wellformed(idea: str, fm_name: str):
    concept = _concept(
        idea,
        [AssemblyConcept("Antrieb", "bewegt", ["Power"], "q")],
    )
    ing = _ingenieur(idea, [FailureMode(fm_name, "Antrieb", "x", "y", "q")])
    spec = map_to_software_spec(concept, ing)

    assert isinstance(spec, SoftwareSpec)
    assert spec.source_idea == idea
    # Idea text is reflected in the summary (consumed, not ignored).
    assert idea.strip() in spec.zusammenfassung
    # Gate invariants hold for every generated spec.
    for comp in spec.embedded_components:
        assert comp.fehler_zustaende
    for api in spec.apis:
        assert api.input and api.output and api.sicherheit
    # The declared failure mode reaches both the component and the testplan.
    assert any(fm_name in e.fehler_zustaende for e in spec.embedded_components)
    assert any(fm_name in t for t in spec.testplan)
