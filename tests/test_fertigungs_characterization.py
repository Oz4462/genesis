"""Characterization tests for fertigungs.map_to_fertigungs_spec (PLAN T01).

These tests pin the facade-killer contract for the manufacturing pipeline:
- the generic (non-jetpack) path must genuinely derive its output from the passed-in
  ``concept`` / ``ingenieur`` fields, so two distinct inputs yield distinguishable
  FertigungsSpecs (the old ``else`` branch returned a fixed FDM/TBD stub independent
  of input — a facade);
- process selection must follow REAL signals: a precision tolerance / metallic material
  adds CNC, a signal-free input does not;
- a blank source_idea must raise ValueError (no fabricated stub for a non-input);
- the DFM cost seam is consumed when present and declared an honest gap (never a
  fabricated price band) when absent;
- the rich jetpack branch is preserved verbatim as a protected regression.
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from gen.cad.cost_model import estimate_fdm_cost
from gen.pipelines.architekt import (
    AssemblyConcept,
    SystemConcept,
    map_to_system_concept,
)
from gen.pipelines.fertigungs import FertigungsSpec, map_to_fertigungs_spec
from gen.pipelines.ingenieur import (
    IngenieurSpec,
    MaterialSpec,
    ToleranceSpec,
    map_to_ingenieur_spec,
)


# --- builders for precise, signal-controlled generic inputs -----------------


def _concept(idea: str, assemblies: list[AssemblyConcept] | None = None) -> SystemConcept:
    return SystemConcept(
        source_idea=idea,
        requirements=[],
        main_assemblies=assemblies or [],
        variants=[],
        open_decisions=[],
        zusammenfassung="characterization",
    )


def _ing(
    *,
    toleranzen: list[ToleranceSpec] | None = None,
    materials: list[MaterialSpec] | None = None,
    cad: list[str] | None = None,
    pruef: list[str] | None = None,
) -> IngenieurSpec:
    return IngenieurSpec(
        source_concept="characterization",
        lastfaelle=[],
        material_hinweise=materials or [],
        toleranzen=toleranzen or [],
        failure_modes=[],
        cad_anforderungen=cad or [],
        pruefplan_hinweise=pruef or [],
        zusammenfassung="characterization",
    )


def _spec_text(spec: FertigungsSpec) -> str:
    """All free text of a spec, for substring/equality assertions."""
    parts = [spec.zusammenfassung, spec.dfm_report_ref or "", spec.kosten_modell.gesamt_est]
    for p in spec.gewaehlte_prozesse:
        parts += [p.name, p.begruendung, p.prozessgrenzen]
    parts += spec.qa_plan.schritte
    return "\n".join(parts)


# --- Facade-killer: two distinct generic inputs must differ -----------------


def test_generic_two_distinct_inputs_differ() -> None:
    """The original facade returned an identical FDM/TBD stub for any non-jetpack idea.

    Two clearly different concept+ingenieur inputs must now produce distinguishable specs.
    """
    a = map_to_fertigungs_spec(
        _concept("a quiet desk lamp", [AssemblyConcept("Base", "holds the lamp", [])]),
        _ing(cad=["Wand 3mm"]),
    )
    b = map_to_fertigungs_spec(
        _concept("a hydroponic garden tower", [AssemblyConcept("Reservoir", "stores water", [])]),
        _ing(cad=["Wand 5mm"], toleranzen=[ToleranceSpec("Bohrung", "H7", "Passung")]),
    )

    assert a != b
    # The difference must show up in actual derived content, not just source_idea.
    assert _spec_text(a) != _spec_text(b)


def test_generic_consumes_concept_and_ingenieur_fields() -> None:
    """source_idea, assembly purpose and a real CAD/tolerance signal must surface."""
    spec = map_to_fertigungs_spec(
        _concept("solar water purifier", [AssemblyConcept("Filter", "removes particles", [])]),
        _ing(cad=["Wand 2.5mm im Filtergehäuse"]),
    )
    text = _spec_text(spec)
    assert "solar water purifier" in text  # the idea is consumed, not just stored
    assert "Filter" in text and "removes particles" in text  # assembly is consumed
    assert "2.5mm" in text  # the real CAD requirement is quoted into prozessgrenzen


def test_generic_precision_tolerance_adds_cnc() -> None:
    """A real precision tolerance must justify (and name) an added CNC process."""
    spec = map_to_fertigungs_spec(
        _concept("precision spindle housing"),
        _ing(toleranzen=[ToleranceSpec("Lagersitz", "H7", "Passung für Kugellager")]),
    )
    names = [p.name for p in spec.gewaehlte_prozesse]
    assert names == ["FDM", "CNC"]
    cnc = next(p for p in spec.gewaehlte_prozesse if p.name == "CNC")
    # The driving real value is embedded in the justification (auditable, not invented).
    assert "H7" in cnc.begruendung and "Lagersitz" in cnc.begruendung


def test_generic_metal_material_adds_cnc() -> None:
    """A metallic material hint must justify an added CNC process naming the material."""
    spec = map_to_fertigungs_spec(
        _concept("aluminium bracket"),
        _ing(materials=[MaterialSpec("Alu 6061-T6")]),
    )
    names = [p.name for p in spec.gewaehlte_prozesse]
    assert "CNC" in names
    cnc = next(p for p in spec.gewaehlte_prozesse if p.name == "CNC")
    assert "Alu 6061-T6" in cnc.begruendung


def test_generic_signal_free_input_abstains_no_cnc_no_fabricated_bound() -> None:
    """Signal-free input ⇒ only the honest FDM baseline, explicit gaps, no fabricated facts."""
    spec = map_to_fertigungs_spec(_concept("a plain box"), _ing())
    assert [p.name for p in spec.gewaehlte_prozesse] == ["FDM"]
    fdm = spec.gewaehlte_prozesse[0]
    # No invented wall thickness — the bound is honestly declared a gap.
    assert "Lücke" in fdm.prozessgrenzen
    # No fabricated cost band.
    assert "€" not in spec.kosten_modell.gesamt_est
    assert "Lücke" in spec.kosten_modell.gesamt_est


# --- Cost seam: consumed when present, honest gap when absent ----------------


def test_generic_consumes_real_dfm_cost_when_present() -> None:
    real_hint = estimate_fdm_cost(20.0, "PLA").summary()
    dfm_report = {"processes": [{"process": "FDM", "cost_hint": real_hint}]}
    spec = map_to_fertigungs_spec(_concept("a small clip"), _ing(), dfm_report=dfm_report)
    assert spec.kosten_modell.gesamt_est == real_hint
    assert "cost_model" in (spec.kosten_modell.quelle or "")


def test_generic_no_dfm_cost_declares_honest_gap() -> None:
    spec = map_to_fertigungs_spec(_concept("a small clip"), _ing(), dfm_report={"processes": []})
    assert "Lücke" in spec.kosten_modell.gesamt_est
    assert "€" not in spec.kosten_modell.gesamt_est
    assert "8-25 EUR" not in spec.kosten_modell.gesamt_est


# --- Negative path: no fabricated stub for a non-input ---------------------


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n  \n"])
def test_blank_source_idea_raises(blank: str) -> None:
    with pytest.raises(ValueError):
        map_to_fertigungs_spec(_concept(blank), _ing())


# --- Protected regression: jetpack branch unchanged ------------------------


def test_jetpack_branch_preserved() -> None:
    """The rich jetpack manufacturing spec must keep its detailed structure verbatim."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher fliegen lässt."
    concept = map_to_system_concept(idee, run_id="t01-jet")
    ing = map_to_ingenieur_spec(concept, run_id="t01-jet")
    real_hint = estimate_fdm_cost(49.0, "PLA").summary()
    dfm_report = {"processes": [{"process": "FDM", "printable": True, "cost_hint": real_hint}]}
    spec = map_to_fertigungs_spec(concept, ing, dfm_report=dfm_report, run_id="t01-jet")

    # Two named processes (FDM primary + CNC alternative) — the jetpack signature.
    assert [p.name for p in spec.gewaehlte_prozesse] == ["FDM", "CNC"]
    assert "Tether" in spec.dfm_report_ref
    assert "Jetpack" in spec.zusammenfassung or "Tether" in spec.zusammenfassung
    # The real cost estimate is still consumed verbatim on the jetpack path.
    assert spec.kosten_modell.gesamt_est == real_hint


# --- Invariant (property-based): non-blank generic idea -> consumed & honest -


@given(
    st.text(min_size=1).filter(
        lambda s: s.strip() and "jetpack" not in s.lower() and "flug" not in s.lower()
    )
)
def test_property_generic_consumes_idea_and_stays_honest(idea: str) -> None:
    """For any non-blank, non-jetpack idea, the spec is well-formed, surfaces the idea,
    and declares an honest cost gap when no DFM report is given (no silent constant stub)."""
    spec = map_to_fertigungs_spec(_concept(idea), _ing())

    assert spec.source_idea == idea
    assert idea in spec.zusammenfassung  # the idea is genuinely consumed
    assert spec.gewaehlte_prozesse  # never empty
    assert "Lücke" in spec.kosten_modell.gesamt_est  # honest abstention without DFM cost


@given(st.text().filter(lambda s: not s.strip()))
def test_property_blank_idea_always_raises(blank: str) -> None:
    with pytest.raises(ValueError):
        map_to_fertigungs_spec(_concept(blank), _ing())
