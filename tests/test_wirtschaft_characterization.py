"""Characterization + facade-killer tests for wirtschaft.map_to_wirtschaft_spec (T01).

Depth-audit goal: the generic (non-jetpack) branch used to return constant TBD/Lücke
content independent of its inputs (PARTIAL-FACADE). These tests PROVE the generic path is
now genuinely input-driven:

1. facade-killer: two DIFFERENT non-jetpack inputs → MEANINGFULLY different output
   (the engineer/concept fields are actually consumed, not a constant stub).
2. honest abstention: a signal-free input yields explicit ``Lücke: …`` strings (no
   fabricated price/volume) instead of a guessed value.
3. NEGATIVE: an empty/whitespace source_idea raises ValueError (keine stillen Defaults).
4. protected regression: the rich jetpack branch is byte-stable.

Inputs are built via the REAL constructors in architekt.py / ingenieur.py; generic-path
ideas avoid the substrings 'jetpack' and 'flug' so they actually hit the generic branch.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

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
    LoadCase,
    MaterialSpec,
    ToleranceSpec,
    map_to_ingenieur_spec,
)
from gen.pipelines.wirtschaft import (
    KostenStruktur,
    Markt,
    WirtschaftSpec,
    map_to_wirtschaft_spec,
)


# --- helpers: build concept/ingenieur with controllable counts via REAL constructors ---

def _concept(
    idea: str,
    *,
    requirements: list[str],
    assemblies: list[str],
    variants: list[str],
    open_decisions: list[str],
) -> SystemConcept:
    return SystemConcept(
        source_idea=idea,
        requirements=[SystemRequirement(text=t, quelle="test") for t in requirements],
        main_assemblies=[
            AssemblyConcept(name=n, purpose=f"trägt {n}", interfaces=["if"], quelle="test")
            for n in assemblies
        ],
        variants=list(variants),
        open_decisions=list(open_decisions),
        zusammenfassung="test concept",
        run_id="t",
    )


def _ingenieur(
    concept: SystemConcept,
    *,
    loadcases: list[str],
    materials: list[str],
    tolerances: list[str],
    failures: list[str],
    pruefplan: list[str],
) -> IngenieurSpec:
    return IngenieurSpec(
        source_concept=concept.source_idea,
        lastfaelle=[LoadCase(n, "desc", "1 kN", "test") for n in loadcases],
        material_hinweise=[MaterialSpec(name=n, quelle="test") for n in materials],
        toleranzen=[ToleranceSpec(f, "H7", "fit", "test") for f in tolerances],
        failure_modes=[FailureMode(n, "asm", "desc", "detect", "test") for n in failures],
        cad_anforderungen=["Struktur"],
        pruefplan_hinweise=list(pruefplan),
        zusammenfassung="test ing",
        run_id="t",
    )


# --- 1. facade-killer: different inputs → meaningfully different output ----------------

def test_generic_two_different_inputs_yield_different_output():
    """Different concept/ingenieur signals must drive different Kosten/Markt/Reparatur —
    proving the inputs are consumed, not echoed into a constant stub."""
    concept_a = _concept(
        "Ein kompakter Wasserfilter für Haushalte",
        requirements=["Sauberes Wasser liefern"],
        assemblies=["Filterkartusche"],
        variants=["MVP"],
        open_decisions=["Membranlieferant offen"],
    )
    ing_a = _ingenieur(
        concept_a,
        loadcases=["Innendruck"],
        materials=["Generic Structural"],
        tolerances=[],
        failures=["Membranriss"],
        pruefplan=["Drucktest"],
    )

    concept_b = _concept(
        "Eine modulare Lagerregal-Anlage für Werkstätten",
        requirements=["500 kg pro Ebene tragen", "Werkzeuglos montierbar", "Erweiterbar"],
        assemblies=["Rahmen", "Querträger", "Bodenplatte"],
        variants=["Basis", "Pro", "XL"],
        open_decisions=["Korrosionsschutz offen", "Steckverbinder offen", "Norm offen"],
    )
    ing_b = _ingenieur(
        concept_b,
        loadcases=["Statische Traglast", "Erdbeben", "Anfahrstoß"],
        materials=["Stahl S235", "Alu 6061"],
        tolerances=["Bohrung H7", "Passung g6"],
        failures=["Beulen", "Schweißnahtbruch", "Kippen"],
        pruefplan=["Lastprüfung", "Sichtprüfung Schweißnaht"],
    )

    spec_a = map_to_wirtschaft_spec(concept_a, ing_a, run_id="A")
    spec_b = map_to_wirtschaft_spec(concept_b, ing_b, run_id="B")

    # Every derived sub-field must differ — a constant stub would make these equal.
    assert spec_a.kosten.prototype != spec_b.kosten.prototype
    assert spec_a.kosten.repair_cost != spec_b.kosten.repair_cost
    assert spec_a.markt.lieferkette != spec_b.markt.lieferkette
    assert spec_a.markt.stueckzahl_ramp != spec_b.markt.stueckzahl_ramp
    assert spec_a.markt.skalierung != spec_b.markt.skalierung
    assert spec_a.reparatur_modell != spec_b.reparatur_modell

    # And the difference reflects the REAL counts (input genuinely consumed).
    assert "3 Baugruppe(n)" in spec_b.kosten.prototype
    assert "1 Baugruppe(n)" in spec_a.kosten.prototype
    assert "Rahmen" in spec_b.markt.lieferkette
    assert "Filterkartusche" in spec_a.markt.lieferkette
    assert "3 Inspektions-/Reparaturpunkt(e)" in spec_b.kosten.repair_cost
    # metal material surfaces as a qualitative cost driver only for B
    assert "metall-/composite" in spec_b.kosten.low_volume
    assert "metall-/composite" not in spec_a.kosten.low_volume


def test_generic_via_real_map_functions_differs_by_idea():
    """End-to-end through the real architekt/ingenieur mappers: two distinct ideas
    (no 'jetpack'/'flug') still produce distinguishable WirtschaftSpecs because the idea
    text propagates through requirements into the market/summary."""
    idea_a = "Ein leiser Tischventilator aus recyceltem Kunststoff"
    idea_b = "Ein faltbarer Lastenanhänger für Fahrräder"

    concept_a = map_to_system_concept(idea_a, run_id="a")
    concept_b = map_to_system_concept(idea_b, run_id="b")
    spec_a = map_to_wirtschaft_spec(concept_a, map_to_ingenieur_spec(concept_a), run_id="a")
    spec_b = map_to_wirtschaft_spec(concept_b, map_to_ingenieur_spec(concept_b), run_id="b")

    assert spec_a.source_idea == idea_a
    assert spec_b.source_idea == idea_b
    assert spec_a.zusammenfassung != spec_b.zusammenfassung
    assert spec_a.markt.zielgruppe != spec_b.markt.zielgruppe
    assert idea_a in spec_a.zusammenfassung
    assert idea_b in spec_b.zusammenfassung


# --- 2. honest abstention: signal-free input → explicit Lücke, no fabricated value -----

def test_generic_no_signal_emits_honest_luecke_not_fabricated_value():
    """A concept/ingenieur with no assemblies, requirements, materials, failures or
    Prüfplan must yield explicit 'Lücke' strings — never a guessed price/volume."""
    concept = _concept(
        "Ein unbestimmtes Objekt",
        requirements=[],
        assemblies=[],
        variants=[],
        open_decisions=[],
    )
    ing = _ingenieur(
        concept,
        loadcases=[],
        materials=[],
        tolerances=[],
        failures=[],
        pruefplan=[],
    )

    spec = map_to_wirtschaft_spec(concept, ing)

    assert "TBD" in spec.kosten.prototype and "Lücke" in spec.kosten.prototype
    assert "Lücke" in spec.kosten.low_volume
    assert "Lücke" in spec.kosten.target_volume
    assert "Lücke" in spec.kosten.repair_cost
    assert "Lücke" in spec.markt.zielgruppe
    assert "Lücke" in spec.markt.lieferkette
    assert "Lücke" in spec.markt.skalierung
    assert "Lücke" in spec.reparatur_modell
    # No fabricated EUR figure must appear on the no-signal path.
    assert "EUR" not in spec.kosten.prototype
    assert "EUR" not in spec.kosten.low_volume


# --- 3. NEGATIVE: empty / whitespace source_idea raises (keine stillen Defaults) -------

@pytest.mark.parametrize("bad_idea", ["", "   ", "\t\n"])
def test_empty_source_idea_raises_valueerror(bad_idea):
    concept = _concept(
        bad_idea,
        requirements=["x"],
        assemblies=["A"],
        variants=["v"],
        open_decisions=["d"],
    )
    ing = _ingenieur(
        concept,
        loadcases=["L"],
        materials=["M"],
        tolerances=[],
        failures=["F"],
        pruefplan=["P"],
    )
    with pytest.raises(ValueError, match="non-empty"):
        map_to_wirtschaft_spec(concept, ing)


# --- 4. protected regression: jetpack branch is byte-stable ----------------------------

def test_jetpack_branch_unchanged():
    """The rich jetpack branch must keep its exact canonical output (protected
    regression: making the generic path real must not alter the demo behavior)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="jet")
    ing = map_to_ingenieur_spec(concept, run_id="jet")
    spec = map_to_wirtschaft_spec(concept, ing, run_id="jet")

    assert spec.kosten == KostenStruktur(
        prototype="8-25 EUR (FDM dominant, from Fertigungs/Realisierungspaket)",
        low_volume="50-150 EUR (small batch CNC + electronics)",
        target_volume="TBD - depends on certification (Lücke: live supplier prices from Wissensbasis)",
        repair_cost="High (tether + battery + harness inspection per Techniker)",
        quelle="Fertigungs + Realisierungspaket + Techniker + PLAN §4",
    )
    assert spec.markt == Markt(
        zielgruppe="Experimental / hobby pilots in controlled areas (post regulatorik approval: certified manned flight)",
        stueckzahl_ramp="1-10 prototypes -> 50-200 low volume (gated by Regulatorik)",
        lieferkette="Motors/batteries from hobby suppliers, tether/custom from specialist (Lücke for full chain)",
        skalierung="Only after full Regulatorik + certification; otherwise limited to experimental use",
        quelle="Regulatorik + PLAN §4 + concept (manned in crowd)",
    )
    assert spec.reparatur_modell == (
        "Per-flight tether inspection + annual full service (Techniker model). "
        "High cost -> low volume market."
    )


# --- public dataclass signatures stay byte-stable (frozen, exact fields) ---------------

def test_public_dataclasses_are_frozen_with_expected_fields():
    spec = map_to_wirtschaft_spec(
        *_concept_and_ing_for_smoke()
    )
    assert isinstance(spec, WirtschaftSpec)
    assert set(KostenStruktur.__dataclass_fields__) == {
        "prototype", "low_volume", "target_volume", "repair_cost", "quelle",
    }
    assert set(Markt.__dataclass_fields__) == {
        "zielgruppe", "stueckzahl_ramp", "lieferkette", "skalierung", "quelle",
    }
    assert set(WirtschaftSpec.__dataclass_fields__) == {
        "source_idea", "kosten", "markt", "reparatur_modell",
        "zusammenfassung", "run_id", "quelle",
    }
    with pytest.raises(FrozenInstanceError):
        spec.source_idea = "mutate"  # type: ignore[misc]


def _concept_and_ing_for_smoke():
    concept = _concept(
        "Eine simple Halterung",
        requirements=["Halten"],
        assemblies=["Bracket"],
        variants=["MVP"],
        open_decisions=["Material offen"],
    )
    ing = _ingenieur(
        concept,
        loadcases=["Last"],
        materials=["Generic Structural"],
        tolerances=[],
        failures=["Bruch"],
        pruefplan=["Lasttest"],
    )
    return concept, ing


# --- PROPERTY-BASED: determinism + source_idea preservation over random ideas ----------

@given(
    idea=st.text(min_size=1, max_size=60).filter(
        lambda s: s.strip() and "jetpack" not in s.lower() and "flug" not in s.lower()
    )
)
def test_property_deterministic_and_preserves_source_idea(idea):
    """For any non-empty, non-jetpack idea: the mapper is deterministic (same input →
    equal output) and faithfully carries the source_idea through (no silent rewrite)."""
    concept = map_to_system_concept(idea)
    ing = map_to_ingenieur_spec(concept)

    spec1 = map_to_wirtschaft_spec(concept, ing, run_id="p")
    spec2 = map_to_wirtschaft_spec(concept, ing, run_id="p")

    assert spec1 == spec2  # determinism (A5 reproducibility)
    assert spec1.source_idea == concept.source_idea
