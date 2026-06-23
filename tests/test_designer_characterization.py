"""Characterization tests for the Designer-Pipeline generic path (T05).

These tests pin the behavior that the generic (non-jetpack) branch of
``map_to_designer_spec`` GENUINELY consumes its inputs instead of returning a
constant stub (the original facade), while the rich jetpack branch is preserved
verbatim as a protected regression.

Facade-killer (the core assertion): two DIFFERENT non-jetpack concepts/specs must
yield DIFFERENT DesignerSpecs, and the derived Bedien-Szenarien must mention the
actual assembly/failure-mode names from the inputs. The old `else` branch returned
fixed lists, so two distinct inputs produced identical output — that is the smell
this test forbids.

Inputs are hand-built ``SystemConcept``/``IngenieurSpec`` objects (NOT the real
mappers' generic fallbacks, which themselves ignore the idea text), so the test
isolates exactly what ``map_to_designer_spec`` derives from its given fields.

NOTE: every constructed idea avoids the substrings 'jetpack' and 'flug' so the
generic branch — not the jetpack branch — is exercised.
"""

from hypothesis import given, strategies as st

from gen.pipelines.architekt import (
    AssemblyConcept,
    SystemConcept,
    map_to_system_concept,
)
from gen.pipelines.ingenieur import (
    FailureMode,
    IngenieurSpec,
    map_to_ingenieur_spec,
)
from gen.pipelines.designer import BedienSzenario, DesignerSpec, map_to_designer_spec


def _concept(idea: str, assemblies: list[AssemblyConcept]) -> SystemConcept:
    """Build a minimal non-jetpack SystemConcept with explicit assemblies."""
    return SystemConcept(
        source_idea=idea,
        requirements=[],
        main_assemblies=assemblies,
        variants=[],
        open_decisions=[],
        zusammenfassung="test concept",
        run_id="char-001",
    )


def _ingenieur(source: str, failure_modes: list[FailureMode]) -> IngenieurSpec:
    """Build a minimal IngenieurSpec carrying explicit failure modes."""
    return IngenieurSpec(
        source_concept=source,
        lastfaelle=[],
        material_hinweise=[],
        toleranzen=[],
        failure_modes=failure_modes,
        cad_anforderungen=[],
        pruefplan_hinweise=[],
        zusammenfassung="test spec",
        run_id="char-001",
    )


def test_generic_path_is_input_driven_two_distinct_inputs_differ():
    """FACADE-KILLER: two different non-jetpack inputs must produce different specs.

    The old generic branch ignored `concept` and `ingenieur`, so this assertion
    would have failed (identical output). It now passes only because the path
    derives content from the actual assemblies + failure modes.
    """
    concept_a = _concept(
        "Ein Greifarm für Laborautomation.",
        [AssemblyConcept("Greifer", "Hält Probe", ["Motor-Schnittstelle"], "arch-a")],
    )
    ing_a = _ingenieur(
        concept_a.source_idea,
        [FailureMode("Motor blockiert", "Greifer", "Greifer klemmt", "Stromüberwachung", "ing-a")],
    )

    concept_b = _concept(
        "Ein fahrbarer Inspektionsroboter.",
        [AssemblyConcept("Fahrwerk", "Bewegt Roboter", ["Rad-Schnittstelle"], "arch-b")],
    )
    ing_b = _ingenieur(
        concept_b.source_idea,
        [FailureMode("Akku überhitzt", "Fahrwerk", "Thermisches Durchgehen", "Temperatursensor", "ing-b")],
    )

    spec_a = map_to_designer_spec(concept_a, ing_a, run_id="char-a")
    spec_b = map_to_designer_spec(concept_b, ing_b, run_id="char-b")

    # Distinct inputs -> distinct derived Bedien-Szenarien (the facade would tie).
    names_a = {b.name for b in spec_a.bedien_szenarien}
    names_b = {b.name for b in spec_b.bedien_szenarien}
    assert names_a != names_b

    # The derived content actually quotes the input fields (input is consumed).
    joined_a = " ".join(b.name + b.beschreibung for b in spec_a.bedien_szenarien)
    joined_b = " ".join(b.name + b.beschreibung for b in spec_b.bedien_szenarien)
    assert "Motor blockiert" in joined_a and "Greifer" in joined_a
    assert "Akku überhitzt" in joined_b and "Fahrwerk" in joined_b
    # And cross-contamination is impossible (no shared constant stub).
    assert "Akku überhitzt" not in joined_a
    assert "Motor blockiert" not in joined_b


def test_failure_mode_detection_flows_into_massnahme():
    """A failure mode's real `detection` becomes the scenario's Massnahme."""
    concept = _concept("Eine Pumpe für Bewässerung.", [])
    ing = _ingenieur(
        concept.source_idea,
        [FailureMode("Dichtung versagt", "Gehäuse", "Leckage", "Drucksensor-Alarm", "ing")],
    )
    spec = map_to_designer_spec(concept, ing)

    scenario = next(b for b in spec.bedien_szenarien if "Dichtung versagt" in b.name)
    assert scenario.massnahme == "Drucksensor-Alarm"


def test_one_scenario_per_failure_mode_and_assembly():
    """Bedien-Szenarien count == #failure_modes + #assemblies (genuinely derived)."""
    assemblies = [
        AssemblyConcept("Basis", "Trägt", ["Mount"], "a"),
        AssemblyConcept("Sensor", "Misst", ["Bus"], "a"),
    ]
    fms = [
        FailureMode("Überlast", "Basis", "Bruch", "Dehnungsmessung", "f"),
        FailureMode("Sensor-Drift", "Sensor", "Falschwert", "Plausibilitätscheck", "f"),
        FailureMode("Kabelbruch", "Sensor", "Signalverlust", "Watchdog", "f"),
    ]
    concept = _concept("Ein modulares Messgerät.", assemblies)
    ing = _ingenieur(concept.source_idea, fms)

    spec = map_to_designer_spec(concept, ing)
    assert len(spec.bedien_szenarien) == len(fms) + len(assemblies)


def test_empty_both_yields_honest_gap_not_fabricated_certainty():
    """NEGATIVE: no assemblies AND no failure modes -> explicit Lücke abstention."""
    concept = _concept("Eine vage Idee ohne Struktur.", [])
    ing = _ingenieur(concept.source_idea, [])

    spec = map_to_designer_spec(concept, ing)

    assert isinstance(spec, DesignerSpec)
    # Every list still non-empty (we emit honest gap markers, not silence)...
    assert spec.ergonomie_anforderungen and spec.form_entscheidungen and spec.bedien_szenarien
    # ...but each is explicitly marked as a Lücke, not fabricated certainty.
    assert all("Lücke" in e.name or "Lücke" in e.annahme for e in spec.ergonomie_anforderungen)
    assert all("Lücke" in b.name or "Lücke" in b.massnahme for b in spec.bedien_szenarien)
    assert "Lücke" in spec.zusammenfassung


def test_only_assemblies_no_failure_modes_still_derives_operation_scenarios():
    """assemblies present, failure_modes empty -> operation scenarios per assembly."""
    concept = _concept(
        "Ein Werkzeug für Montage.",
        [AssemblyConcept("Griff", "Hand-Interface", ["Hand"], "a")],
    )
    ing = _ingenieur(concept.source_idea, [])
    spec = map_to_designer_spec(concept, ing)

    assert len(spec.bedien_szenarien) == 1
    assert "Griff" in spec.bedien_szenarien[0].name


def test_jetpack_branch_preserved_verbatim():
    """PROTECTED REGRESSION: the rich jetpack branch is unchanged."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher fliegen lässt."
    concept = map_to_system_concept(idee, run_id="jet")
    ing = map_to_ingenieur_spec(concept, run_id="jet")
    spec = map_to_designer_spec(concept, ing, run_id="jet")

    # The detailed jetpack output (2 ergo, 2 form, 3 bedien) must survive intact.
    assert len(spec.ergonomie_anforderungen) == 2
    assert len(spec.form_entscheidungen) == 2
    assert len(spec.bedien_szenarien) == 3
    assert any("Harness" in e.name for e in spec.ergonomie_anforderungen)
    assert any("Missbrauch" in b.name for b in spec.bedien_szenarien)
    assert "Jetpack" in spec.zusammenfassung


# --- Property-based invariant: every prior-stone item is represented exactly once.
# 'flug'/'jetpack'-free identifiers keep the generic branch active for all draws.
_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65),
    min_size=1,
    max_size=12,
).filter(lambda s: "jetpack" not in s.lower() and "flug" not in s.lower())


@given(
    assembly_names=st.lists(_safe_text, max_size=5),
    fm_names=st.lists(_safe_text, max_size=5),
)
def test_property_each_input_item_maps_to_one_scenario(assembly_names, fm_names):
    """Invariant: for any non-empty generic input, #scenarios == #fm + #assemblies,
    and every input name appears in some scenario (no silent drop, no fabrication)."""
    assemblies = [AssemblyConcept(n, "Zweck", ["Iface"], "a") for n in assembly_names]
    fms = [FailureMode(n, "BG", "Beschr", "Detect", "f") for n in fm_names]
    concept = _concept("Ein generisches System ohne Schlagwort.", assemblies)
    ing = _ingenieur(concept.source_idea, fms)

    spec = map_to_designer_spec(concept, ing)

    if not assemblies and not fms:
        # Honest-gap path: a single explicit Lücke scenario, nothing fabricated.
        assert len(spec.bedien_szenarien) == 1
        assert "Lücke" in spec.bedien_szenarien[0].name
        return

    assert len(spec.bedien_szenarien) == len(fms) + len(assemblies)
    joined = " ".join(b.name for b in spec.bedien_szenarien)
    for name in assembly_names + fm_names:
        assert name in joined


def test_existing_generic_idea_still_honest_via_real_mappers():
    """Regression on the original public contract: a non-jetpack idea routed through
    the real mappers still yields an honest, Lücke-marked DesignerSpec."""
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="gen")
    ing = map_to_ingenieur_spec(concept, run_id="gen")
    spec = map_to_designer_spec(concept, ing, run_id="gen")

    assert spec.bedien_szenarien  # at least one (derived from the 1 generic assembly)
    assert all(isinstance(b, BedienSzenario) for b in spec.bedien_szenarien)
    assert "Lücke" in spec.zusammenfassung
