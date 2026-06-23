"""Characterization tests for the Regulatorik-Pipeline generic path (T03).

These tests pin the behavior that the generic (non-jetpack) branch of
``map_to_regulatorik_spec`` GENUINELY consumes its inputs instead of returning a
constant stub (the original facade), while the rich jetpack branch is preserved
verbatim as a protected regression.

Facade-killer (the core assertion): two DIFFERENT non-jetpack concepts/specs must
yield DIFFERENT RegulatorikSpecs, and the derived Risiken must mention the actual
failure_mode names / load names and the detection strings from the inputs.
The old `else` branch returned fixed "Generic failure" + fixed "ISO 12100", so
two distinct inputs produced identical output (plus blind ISO claim).

Inputs are hand-built ``SystemConcept``/``IngenieurSpec`` objects (NOT the real
mappers' generic fallbacks), so the test isolates exactly what the regulatorik
mapper derives from its given fields.

NOTE: every constructed idea avoids the substrings 'jetpack' and 'flug' (and
assembly names avoid them) so the generic branch — not the jetpack branch — is
exercised.
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
    LoadCase,
    map_to_ingenieur_spec,
)
from gen.pipelines.regulatorik import (
    RegulatorikSpec,
    Risiko,
    map_to_regulatorik_spec,
)


def _concept(idea: str, assemblies: list[AssemblyConcept]) -> SystemConcept:
    """Build a minimal non-jetpack SystemConcept with explicit assemblies."""
    return SystemConcept(
        source_idea=idea,
        requirements=[],
        main_assemblies=assemblies,
        variants=[],
        open_decisions=[],
        zusammenfassung="test concept",
        run_id="char-reg-001",
    )


def _ingenieur(source: str, failure_modes: list[FailureMode], lastfaelle: list[LoadCase] | None = None) -> IngenieurSpec:
    """Build a minimal IngenieurSpec carrying explicit failure modes and load cases."""
    return IngenieurSpec(
        source_concept=source,
        lastfaelle=lastfaelle or [],
        material_hinweise=[],
        toleranzen=[],
        failure_modes=failure_modes,
        cad_anforderungen=[],
        pruefplan_hinweise=[],
        zusammenfassung="test spec",
        run_id="char-reg-001",
    )


def test_generic_path_is_input_driven_two_distinct_inputs_differ():
    """FACADE-KILLER: two different non-jetpack inputs must produce different specs.

    The old generic branch ignored `concept` and `ingenieur` (always same ISO + "Generic failure").
    Now the path derives risiken + warns + summary from the actual fms + lastfaelle + assemblies.
    """
    concept_a = _concept(
        "Ein Greifarm für Laborautomation.",
        [AssemblyConcept("Greifer", "Hält Probe", ["Motor-Schnittstelle"], "arch-a")],
    )
    ing_a = _ingenieur(
        concept_a.source_idea,
        [FailureMode("Motor blockiert", "Greifer", "Greifer klemmt", "Stromüberwachung", "ing-a")],
        [LoadCase("Greiflast", "Maximale Haltekraft", "150 N", "arch-a")],
    )

    concept_b = _concept(
        "Ein fahrbarer Inspektionsroboter.",
        [AssemblyConcept("Fahrwerk", "Bewegt Roboter", ["Rad-Schnittstelle"], "arch-b")],
    )
    ing_b = _ingenieur(
        concept_b.source_idea,
        [FailureMode("Akku überhitzt", "Fahrwerk", "Thermisches Durchgehen", "Temperatursensor", "ing-b")],
        [LoadCase("Fahr-Last", "Bodenkontakt", "800 N", "arch-b")],
    )

    spec_a = map_to_regulatorik_spec(concept_a, ing_a, run_id="char-a")
    spec_b = map_to_regulatorik_spec(concept_b, ing_b, run_id="char-b")

    # Distinct inputs -> distinct derived risiken (the facade would tie them).
    names_a = {r.name for r in spec_a.risiken}
    names_b = {r.name for r in spec_b.risiken}
    assert names_a != names_b

    # The derived content actually quotes the input fields (input is consumed).
    joined_a = " ".join(r.name + " " + r.beschreibung + " " + r.massnahme for r in spec_a.risiken)
    joined_b = " ".join(r.name + " " + r.beschreibung + " " + r.massnahme for r in spec_b.risiken)
    assert "Motor blockiert" in joined_a and "Stromüberwachung" in joined_a
    assert "Akku überhitzt" in joined_b and "Temperatursensor" in joined_b
    # Cross-contamination impossible (no shared constant stub).
    assert "Akku überhitzt" not in joined_a
    assert "Motor blockiert" not in joined_b

    # Warnings and summary also differ and mention the driving idea text / assembly.
    assert "Greifarm" in spec_a.zusammenfassung or "Greifer" in " ".join(spec_a.warnhinweise)
    assert "Inspektionsroboter" in spec_b.zusammenfassung or "Fahrwerk" in " ".join(spec_b.warnhinweise)


def test_failure_mode_detection_flows_into_risiko_massnahme():
    """A failure mode's real `detection` becomes the Risiko's massnahme (1:1 derivation)."""
    concept = _concept("Eine Pumpe für Bewässerung.", [])
    ing = _ingenieur(
        concept.source_idea,
        [FailureMode("Dichtung versagt", "Gehäuse", "Leckage", "Drucksensor-Alarm", "ing")],
        [],
    )
    spec = map_to_regulatorik_spec(concept, ing)

    risiko = next(r for r in spec.risiken if "Dichtung versagt" in r.name)
    assert risiko.massnahme == "Drucksensor-Alarm"
    assert "Human sign-off required" in risiko.freigabe


def test_load_case_derives_into_risiko():
    """Load cases produce distinct Risiken carrying kraft_oder_moment."""
    concept = _concept("Ein Presswerkzeug.", [AssemblyConcept("Stempel", "Formt Blech", ["Führung"], "a")])
    ing = _ingenieur(
        concept.source_idea,
        [],
        [LoadCase("Presskraft", "Max. Formkraft", "120 kN", "ingenieur")],
    )
    spec = map_to_regulatorik_spec(concept, ing)

    risiko = next(r for r in spec.risiken if "Presskraft" in r.name or "120 kN" in r.beschreibung)
    assert "120 kN" in risiko.beschreibung
    assert "Einhaltung der spezifizierten Last" in risiko.massnahme


def test_assembly_names_appear_in_warnings_and_summary():
    """main_assemblies drive warnhinweise and are reflected in summary."""
    assemblies = [
        AssemblyConcept("Basisrahmen", "Trägt alle Lasten", ["Boden", "Antrieb"], "a"),
        AssemblyConcept("Sensorarm", "Misst Position", ["CAN"], "a"),
    ]
    concept = _concept("Ein Messsystem für Qualitätskontrolle.", assemblies)
    ing = _ingenieur(concept.source_idea, [], [LoadCase("Eigengewicht", "Statik", "50 kg", "a")])
    spec = map_to_regulatorik_spec(concept, ing)

    all_warn = " ".join(spec.warnhinweise)
    assert "Basisrahmen" in all_warn and "Sensorarm" in all_warn
    assert "2 Baugruppe" in spec.zusammenfassung or "Basisrahmen" in spec.zusammenfassung


def test_norm_is_honest_gap_for_generic_no_specific_signal():
    """Generic non-jetpack without domain-specific signals uses explicit gap norm, not ISO 12100."""
    concept = _concept("Ein einfacher mechanischer Hebel.", [])
    ing = _ingenieur(concept.source_idea, [], [LoadCase("Hebelkraft", "Betätigung", "200 N", "g")])
    spec = map_to_regulatorik_spec(concept, ing)

    assert len(spec.normen) >= 1
    assert any("keine spezifische Norm ableitbar" in n.name for n in spec.normen)
    # Never the blind ISO for generic.
    assert not any("ISO 12100" in n.name for n in spec.normen)


def test_empty_signal_yields_value_error_not_canned_stub():
    """NEGATIVE: blank source_idea or no actionable signal -> ValueError (no fabricated stub)."""
    # Blank source_idea
    bad_concept = _concept("", [AssemblyConcept("X", "Y", [], None)])
    ing_ok = _ingenieur("x", [FailureMode("f", "b", "d", "det", None)], [])
    try:
        map_to_regulatorik_spec(bad_concept, ing_ok)
        assert False, "should have raised"
    except ValueError as e:
        assert "source_idea" in str(e).lower() or "non-empty" in str(e).lower()

    # Non-blank idea but zero actionable (no fms, no lastfaelle, no assemblies)
    empty_concept = _concept("Vage Idee ohne Strukturangabe.", [])
    empty_ing = _ingenieur(empty_concept.source_idea, [], [])
    try:
        map_to_regulatorik_spec(empty_concept, empty_ing)
        assert False, "should have raised for no actionable signal"
    except ValueError as e:
        assert "actionable signal" in str(e) or "failure_modes" in str(e).lower()


def test_only_load_cases_without_fms_still_derives():
    """lastfaelle present (fms empty) -> still produces derived Risiken (input consumed)."""
    concept = _concept("Ein Hebewerk.", [AssemblyConcept("Seilzug", "Hebt Last", ["Motor"], "a")])
    ing = _ingenieur(concept.source_idea, [], [LoadCase("Hub-Last", "Nennlast", "5 t", "g")])
    spec = map_to_regulatorik_spec(concept, ing)

    assert any("Hub-Last" in r.name or "5 t" in r.beschreibung for r in spec.risiken)
    assert len(spec.risiken) >= 1


def test_jetpack_branch_preserved_verbatim():
    """PROTECTED REGRESSION: the rich jetpack branch is unchanged (L3 seam)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="jet-reg")
    ing = map_to_ingenieur_spec(concept, run_id="jet-reg")
    spec = map_to_regulatorik_spec(concept, ing, run_id="jet-reg")

    assert isinstance(spec, RegulatorikSpec)
    assert spec.source_idea == idee
    assert len(spec.normen) >= 1
    assert any("EASA" in n.name or "ISO 12100" in n.name for n in spec.normen)

    assert len(spec.risiken) >= 1
    assert any("tether" in r.name.lower() or "battery" in r.name.lower() for r in spec.risiken)
    assert any("human" in r.freigabe.lower() or "sign-off" in r.freigabe.lower() for r in spec.risiken)

    assert len(spec.warnhinweise) >= 1
    assert "WARNING" in " ".join(spec.warnhinweise).upper()
    assert "pilot" in spec.freigabe_prozess.lower() or "human" in spec.freigabe_prozess.lower()
    assert "liability" in spec.haftungsgrenzen.lower() or "operator" in spec.haftungsgrenzen.lower()

    assert "Jetpack" in spec.zusammenfassung or "tether" in spec.zusammenfassung.lower()
    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")


# --- Property-based invariants (Hypothesis) ---
# Safe text excludes jetpack/flug substrings so generic branch is always exercised.
_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65),
    min_size=1,
    max_size=12,
).filter(lambda s: "jetpack" not in s.lower() and "flug" not in s.lower())


@given(
    assembly_names=st.lists(_safe_text, max_size=4, unique=True),
    fm_names=st.lists(_safe_text, max_size=4, unique=True),
    lc_names=st.lists(_safe_text, max_size=3, unique=True),
)
def test_property_derived_risiken_reflect_all_inputs(assembly_names, fm_names, lc_names):
    """Invariant: derived risiken count >= #fms + #lastfaelle (at least one per),
    and every input name from fms/lastfaelle appears in the output names/beschreibungen.
    Also: gap norm always present; never ISO 12100 in generic.
    """
    assemblies = [AssemblyConcept(n, "Zweck", ["Iface"], "a") for n in assembly_names]
    fms = [FailureMode(n, "BG", "Beschreibung " + n, "Detect-" + n, "f") for n in fm_names]
    lcs = [LoadCase(n, "Last " + n, "42 N", "l") for n in lc_names]

    concept = _concept("Ein generisches mechanisches System ohne Kennwort.", assemblies)
    ing = _ingenieur(concept.source_idea, fms, lcs)

    if not assembly_names and not fm_names and not lc_names:
        # Contract: no actionable signal (and no assemblies) -> ValueError, not fabricated canned result.
        # (Hypothesis can draw the empty case; we assert the documented error path.)
        try:
            map_to_regulatorik_spec(concept, ing)
            assert False, "expected ValueError for zero-signal input"
        except ValueError:
            return

    spec = map_to_regulatorik_spec(concept, ing)

    # At minimum one norm and it must be the honest gap (no blind ISO).
    assert len(spec.normen) >= 1
    assert any("keine spezifische Norm ableitbar" in n.name for n in spec.normen)
    assert not any("ISO 12100" in (n.name or "") for n in spec.normen)

    total_drivers = len(fms) + len(lcs)
    if total_drivers > 0:
        assert len(spec.risiken) >= total_drivers
        joined = " ".join(r.name + " " + r.beschreibung + " " + r.massnahme for r in spec.risiken)
        for name in fm_names + lc_names:
            assert name in joined, f"input name {name} must appear in derived risks"

    # Summary must mention counts (proves consumption of lengths).
    assert str(len(fms)) in spec.zusammenfassung or str(len(lcs)) in spec.zusammenfassung or str(len(assemblies)) in spec.zusammenfassung


def test_existing_generic_idea_still_honest_via_real_mappers():
    """Regression on public contract: a non-jetpack idea through real mappers still produces
    an honest gap-norm + derived content (from the minimal load case the generic ingenieur emits).
    """
    idee = "Ein portables Gerät für Tests."
    concept = map_to_system_concept(idee, run_id="gen-reg")
    ing = map_to_ingenieur_spec(concept, run_id="gen-reg")
    spec = map_to_regulatorik_spec(concept, ing, run_id="gen-reg")

    assert isinstance(spec, RegulatorikSpec)
    assert len(spec.normen) >= 1
    assert any("keine spezifische Norm ableitbar" in n.name for n in spec.normen)
    # The generic ingenieur emits one lastfaelle -> at least one derived risk
    assert len(spec.risiken) >= 1
    # Legacy expectation: Lücke mention or Generic in summary
    assert "Lücke" in spec.zusammenfassung or "generisch" in spec.zusammenfassung.lower() or "input-getrieben" in spec.zusammenfassung.lower()
    assert "§4" in (spec.quelle or "") or "PLAN" in (spec.quelle or "")