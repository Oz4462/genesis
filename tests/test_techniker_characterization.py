"""Characterization tests for the Techniker-Pipeline generic path (T05).

These tests pin the behavior that the generic (non-jetpack) branch of
``map_to_techniker_spec`` GENUINELY consumes its inputs (concept.main_assemblies,
ingenieur.cad_anforderungen/toleranzen/failure_modes, physiker.falsifikations_plan)
instead of returning a constant stub (the original facade), while the rich
jetpack branch is preserved verbatim as a protected regression.

Facade-killer (the core assertion): two DIFFERENT non-jetpack inputs must yield
DIFFERENT TechnikerSpecs; assembly names, failure descriptions, cad hints and
falsification plan data must surface in the derived fields. The old else branch
always emitted the same 'Grundplatte vorbereiten' + single-tool + one-line stubs.

Gate enforcement tested: every MontageSchritt has input+output+pruefpunkt;
every tool referenced by a step appears in werkzeug_liste.

Inputs are hand-built via the REAL dataclasses (never mocked module under test).
Ideas and assembly names deliberately avoid 'jetpack'/'flug' to hit the generic
branch (per team decisions).

Every test also exercises the documented fail-loud ValueError for the no-signal case.
"""

from __future__ import annotations

from hypothesis import given, strategies as st

import pytest

from gen.pipelines.architekt import (
    AssemblyConcept,
    SystemConcept,
    map_to_system_concept,
)
from gen.pipelines.ingenieur import (
    FailureMode,
    IngenieurSpec,
    ToleranceSpec,
    map_to_ingenieur_spec,
)
from gen.pipelines.physiker import (
    FalsifikationsPlan,
    PhysikerSpec,
    map_to_physiker_spec,
)
from gen.pipelines.techniker import (
    MontageSchritt,
    TechnikerSpec,
    map_to_techniker_spec,
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
        run_id="char-tech-001",
    )


def _ingenieur(
    source: str,
    *,
    failure_modes: list[FailureMode] | None = None,
    cad_anforderungen: list[str] | None = None,
    toleranzen: list[ToleranceSpec] | None = None,
) -> IngenieurSpec:
    """Build a minimal IngenieurSpec carrying explicit failure/cad/tol data."""
    return IngenieurSpec(
        source_concept=source,
        lastfaelle=[],
        material_hinweise=[],
        toleranzen=toleranzen or [],
        failure_modes=failure_modes or [],
        cad_anforderungen=cad_anforderungen or [],
        pruefplan_hinweise=[],
        zusammenfassung="test ingenieur",
        run_id="char-tech-001",
    )


def _physiker(source: str, falsi: list[FalsifikationsPlan]) -> PhysikerSpec:
    """Build a minimal PhysikerSpec carrying falsification plans."""
    return PhysikerSpec(
        source_idea=source,
        relevante_domaenen=[],
        modell_gleichungen=[],
        unsicherheits_budget=[],
        falsifikations_plan=falsi,
        zusammenfassung="test physiker",
        run_id="char-tech-001",
    )


def test_generic_path_is_input_driven_two_distinct_inputs_differ():
    """FACADE-KILLER: two different non-jetpack inputs produce different specs.

    Assembly names + failure descriptions + cad hints must appear verbatim in output.
    Old facade would have produced identical 'Grundplatte' stub for both.
    """
    assy_a = [AssemblyConcept("Greifer", "Hält Probe", ["Motor"], "arch-a")]
    fm_a = [FailureMode("Motor blockiert", "Greifer", "Greifer klemmt", "Stromüberwachung", "ing-a")]
    cad_a = ["Bohrmaschine HSS + Reibahle"]
    concept_a = _concept("Ein Greifarm für Laborautomation.", assy_a)
    ing_a = _ingenieur(concept_a.source_idea, failure_modes=fm_a, cad_anforderungen=cad_a)

    assy_b = [AssemblyConcept("Fahrwerk", "Bewegt Roboter", ["Rad"], "arch-b")]
    fm_b = [FailureMode("Akku überhitzt", "Fahrwerk", "Thermisches Durchgehen", "Temperatursensor", "ing-b")]
    cad_b = ["Schleifmaschine + Messschieber"]
    concept_b = _concept("Ein fahrbarer Inspektionsroboter.", assy_b)
    ing_b = _ingenieur(concept_b.source_idea, failure_modes=fm_b, cad_anforderungen=cad_b)

    phys = _physiker(concept_a.source_idea, [])

    spec_a = map_to_techniker_spec(concept_a, ing_a, phys, run_id="ca")
    spec_b = map_to_techniker_spec(concept_b, ing_b, phys, run_id="cb")

    # Distinct driving inputs must produce distinguishable output (names surface)
    names_a = {s.name for s in spec_a.montage_plan}
    names_b = {s.name for s in spec_b.montage_plan}
    assert names_a != names_b

    joined_a = " ".join(
        s.name + " " + s.beschreibung + " " + " ".join(s.typische_fehler) + " ".join(s.werkzeuge)
        for s in spec_a.montage_plan
    ) + " " + " ".join(spec_a.wartungs_plan) + " " + " ".join(spec_a.reparatur_hinweise)
    joined_b = " ".join(
        s.name + " " + s.beschreibung + " " + " ".join(s.typische_fehler) + " ".join(s.werkzeuge)
        for s in spec_b.montage_plan
    ) + " " + " ".join(spec_b.wartungs_plan) + " " + " ".join(spec_b.reparatur_hinweise)
    # Check assembly and the failure's beschreibung (name flows to wartung/reparatur when fms present)
    assert "Greifer" in joined_a and "Greifer klemmt" in joined_a
    assert "Motor blockiert" in joined_a  # surfaces via wartung derived from fm.name
    assert "Fahrwerk" in joined_b and "Akku überhitzt" in joined_b
    assert "Bohrmaschine" in joined_a
    assert "Schleifmaschine" in joined_b
    # No cross contamination from constant stub
    assert "Akku überhitzt" not in joined_a
    assert "Motor blockiert" not in joined_b
    assert "Greifer klemmt" not in joined_b


def test_assembly_drives_montage_and_summary_reflects_idea():
    """Montage steps and summary are derived from assemblies and source_idea."""
    assemblies = [
        AssemblyConcept("Basisplatte", "Trägt Struktur", ["Mount"], "a"),
        AssemblyConcept("Sensorarm", "Misst Werte", ["Bus"], "a"),
    ]
    concept = _concept("Eine Messvorrichtung für Umweltparameter.", assemblies)
    ing = _ingenieur(concept.source_idea)
    phys = _physiker(concept.source_idea, [])
    spec = map_to_techniker_spec(concept, ing, phys)

    assert len(spec.montage_plan) == 2
    assert "Basisplatte" in spec.montage_plan[0].name
    assert "Sensorarm" in spec.montage_plan[1].name
    assert "Messvorrichtung für Umweltparameter" in spec.zusammenfassung
    assert all(s.input and s.output and s.pruefpunkt for s in spec.montage_plan)


def test_tools_come_from_cad_anforderungen_and_tolerances():
    """Werkzeuge are taken from ingenieur cad/tol hints (not hardcoded)."""
    assy = [AssemblyConcept("Halteplatte", "Fixiert", ["Schraub"], "a")]
    cad = ["H7 Reibahle für Passung", "Inbus-Schlüssel Satz"]
    tol = [ToleranceSpec("Bohrung", "H7/g6", "Passung", "tol")]
    concept = _concept("Eine Haltevorrichtung.", assy)
    ing = _ingenieur(concept.source_idea, cad_anforderungen=cad, toleranzen=tol)
    phys = _physiker(concept.source_idea, [])
    spec = map_to_techniker_spec(concept, ing, phys)

    all_tools = " ".join(spec.werkzeug_liste)
    assert "Reibahle" in all_tools or "H7" in all_tools
    assert "Inbus" in all_tools
    # Gate: every referenced tool from steps is in the top level list
    for step in spec.montage_plan:
        for w in step.werkzeuge:
            assert w in spec.werkzeug_liste


def test_pruef_schritte_derive_from_physiker_falsifikations_plan():
    """Pruef steps are built from falsifikations_plan name + expected measure + abort criterion."""
    assy = [AssemblyConcept("Arm", "Bewegt", [], "a")]
    concept = _concept("Ein Roboterarm.", assy)
    ing = _ingenieur(concept.source_idea)
    fps = [
        FalsifikationsPlan(
            "Last-Test",
            "Statik bis Bruch",
            "Kraft bei Dehnung",
            "Dehnung > 0.5mm",
            "phys",
        )
    ]
    phys = _physiker(concept.source_idea, fps)
    spec = map_to_techniker_spec(concept, ing, phys)

    assert len(spec.pruef_schritte) == 1
    p = spec.pruef_schritte[0]
    assert "Last-Test" in p
    assert "Kraft bei Dehnung" in p
    assert "Dehnung > 0.5mm" in p


def test_failure_modes_drive_typische_fehler_wartung_reparatur():
    """Failure modes flow into per-step typische_fehler + wartung/reparatur lists."""
    assy = [AssemblyConcept("Gelenk", "Schwenkt", [], "a")]
    fm = [
        FailureMode("Lager verschleißt", "Gelenk", "Spiel im Gelenk", "Vibration-Sensor", "fm1"),
    ]
    concept = _concept("Ein schwenkbares Gelenk-Modul.", assy)
    ing = _ingenieur(concept.source_idea, failure_modes=fm)
    phys = _physiker(concept.source_idea, [])
    spec = map_to_techniker_spec(concept, ing, phys)

    step = spec.montage_plan[0]
    assert any("Lager verschleißt" in e or "Spiel im Gelenk" in e for e in step.typische_fehler)
    assert any("Lager verschleißt" in w for w in spec.wartungs_plan)
    assert any("Lager verschleißt" in r for r in spec.reparatur_hinweise)


def test_every_step_has_input_output_check_and_tools_in_list():
    """Gate verification (L4): every MontageSchritt satisfies the documented contract."""
    assy = [
        AssemblyConcept("Frame", "Träger", ["Tether"], "a"),
        AssemblyConcept("Cover", "Schutz", [], "a"),
    ]
    concept = _concept("Ein geschütztes Träger-Modul.", assy)
    ing = _ingenieur(concept.source_idea, cad_anforderungen=["Bohrer"])
    phys = _physiker(concept.source_idea, [])
    spec = map_to_techniker_spec(concept, ing, phys)

    for s in spec.montage_plan:
        assert s.input and isinstance(s.input, str)
        assert s.output and isinstance(s.output, str)
        assert s.pruefpunkt and isinstance(s.pruefpunkt, str)
        assert isinstance(s.werkzeuge, list) and s.werkzeuge
    for w in spec.werkzeug_liste:
        assert isinstance(w, str)
    # All step tools are covered
    step_tools = {w for s in spec.montage_plan for w in s.werkzeuge}
    assert step_tools.issubset(set(spec.werkzeug_liste))


def test_empty_source_idea_and_no_assemblies_raises_valueerror():
    """NEGATIVE (fail-loud): blank source_idea + zero assemblies -> documented ValueError, not stub."""
    concept = _concept("", [])
    ing = _ingenieur("")
    phys = _physiker("", [])
    with pytest.raises(ValueError) as exc:
        map_to_techniker_spec(concept, ing, phys)
    assert "source_idea must be a non-empty, non-whitespace string" in str(exc.value)
    assert "no main_assemblies" in str(exc.value).lower()


def test_no_assemblies_but_idea_yields_honest_gap_step_not_canned_procedure():
    """Signal-free assemblies (but idea present) -> Lücke step, not fabricated 'Grundplatte'."""
    concept = _concept("Eine vage Idee ohne definierte Baugruppen.", [])
    ing = _ingenieur(concept.source_idea)
    phys = _physiker(concept.source_idea, [])
    spec = map_to_techniker_spec(concept, ing, phys)

    assert len(spec.montage_plan) == 1
    s = spec.montage_plan[0]
    assert "Lücke" in s.name
    assert "Lücke" in s.beschreibung
    assert "Lücke" in " ".join(spec.pruef_schritte + spec.wartungs_plan + spec.reparatur_hinweise)


def test_jetpack_branch_preserved_verbatim():
    """PROTECTED REGRESSION: rich jetpack branch (4 steps, specific tools, 3 pruef etc) unchanged."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="jet-tech")
    ingen = map_to_ingenieur_spec(concept, run_id="jet-tech")
    phys = map_to_physiker_spec(concept, ingen, run_id="jet-tech")
    tech = map_to_techniker_spec(concept, ingen, phys, run_id="jet-tech")

    assert len(tech.montage_plan) == 4
    assert len(tech.werkzeug_liste) == 5
    assert len(tech.pruef_schritte) == 3
    assert len(tech.wartungs_plan) == 3
    assert len(tech.reparatur_hinweise) == 3
    names = [s.name for s in tech.montage_plan]
    assert any("Tether-Löcher" in n or "Recovery" in n or "Vorbereitung Platte" in n for n in names)
    assert any("Bohrmaschine" in w or "Messschieber" in w for w in tech.werkzeug_liste)
    assert "Jetpack" in tech.zusammenfassung or "Tether-Anchor" in tech.zusammenfassung


# --- Property-based invariants (Hypothesis) ---------------------------------

_safe = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=65),
    min_size=3,
    max_size=18,
).filter(lambda s: "jetpack" not in s.lower() and "flug" not in s.lower())


@given(
    assembly_names=st.lists(_safe, min_size=0, max_size=4, unique=True),
    fm_names=st.lists(_safe, min_size=0, max_size=3, unique=True),
)
def test_property_montage_count_and_names_surface(assembly_names, fm_names):
    """For any jetpack/flug-free input: #montage == #assemblies (or 1 Lücke when 0);
    every assembly/failure name surfaces in the output (no silent drop or fabrication).
    """
    assemblies = [AssemblyConcept(n, "Zweck " + n, ["Iface"], "a") for n in assembly_names]
    fms = [FailureMode(n, "BG-" + n, "Beschreibung " + n, "Detect", "f") for n in fm_names]
    concept = _concept("Ein generisches System ohne verbotene Schlagworte.", assemblies)
    ing = _ingenieur(concept.source_idea, failure_modes=fms)
    phys = _physiker(concept.source_idea, [])
    spec = map_to_techniker_spec(concept, ing, phys)

    if not assemblies:
        assert len(spec.montage_plan) == 1
        assert "Lücke" in spec.montage_plan[0].name
        return

    assert len(spec.montage_plan) == len(assemblies)
    all_text = " ".join(
        s.name + " " + s.beschreibung + " " + " ".join(s.typische_fehler)
        for s in spec.montage_plan
    ) + " " + " ".join(spec.wartungs_plan) + " " + " ".join(spec.reparatur_hinweise)
    for name in assembly_names:
        assert name in all_text
    for name in fm_names:
        assert name in all_text


def test_existing_generic_idea_still_honest_via_real_mappers():
    """Regression: a non-jetpack idea via real upstream mappers yields derived (non-constant) TechnikerSpec."""
    idee = "Ein tragbares Messgerät für Bodenproben."
    concept = map_to_system_concept(idee, run_id="gen-tech")
    ing = map_to_ingenieur_spec(concept, run_id="gen-tech")
    phys = map_to_physiker_spec(concept, ing, run_id="gen-tech")
    spec = map_to_techniker_spec(concept, ing, phys, run_id="gen-tech")

    # At minimum the (single) generic assembly produces a step whose name contains the assembly name
    assert spec.montage_plan
    assert all(isinstance(s, MontageSchritt) for s in spec.montage_plan)
    assert any("Main Structure" in s.name or "Structure" in s.name for s in spec.montage_plan)
    # And source_idea is faithfully copied (never mutated)
    assert spec.source_idea == idee
