"""Characterization tests for the Physiker-Pipeline generic branch (T02).

These tests pin the behavior that the generic (non-jetpack) branch of
``map_to_physiker_spec`` GENUINELY consumes its inputs (concept + ingenieur)
instead of returning a constant stub (the original facade), while the rich
jetpack branch is preserved verbatim as a protected regression.

Facade-killer (the core assertion): two DIFFERENT non-jetpack concepts + ingenieur
specs (carrying distinct lastfaelle / failure_modes) must yield DIFFERENT
PhysikerSpecs, and the derived domains / falsi / budgets must mention the actual
load-case names and failure names from the inputs. The old else branch returned
fixed "Grundmechanik", "F=ma", "±5% Masse", one generic falsi — two inputs produced
identical output.

Inputs are hand-built ``SystemConcept``/``IngenieurSpec`` objects using the real
dataclass constructors (never the mappers' own generic fallbacks) so the test
isolates exactly what ``map_to_physiker_spec`` derives from the supplied fields.

NOTE: every constructed idea + assembly names avoid the substrings 'jetpack' and 'flug'
(and 'jetpack' assembly names) so the generic branch — not the jetpack branch — is exercised.

Property-based tests (Hypothesis) assert the universal facade-killer invariants.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make src importable (standard pattern in characterization tests)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hypothesis import given, strategies as st  # noqa: E402

from gen.pipelines.architekt import (  # noqa: E402
    AssemblyConcept,
    SystemConcept,
    map_to_system_concept,
)
from gen.pipelines.ingenieur import (  # noqa: E402
    FailureMode,
    IngenieurSpec,
    LoadCase,
    MaterialSpec,
    map_to_ingenieur_spec,
)
from gen.pipelines.physiker import (  # noqa: E402
    PhysikerSpec,
    map_to_physiker_spec,
)


def _concept(idea: str, assemblies: list[AssemblyConcept] | None = None) -> SystemConcept:
    """Build a minimal non-jetpack SystemConcept with explicit assemblies."""
    return SystemConcept(
        source_idea=idea,
        requirements=[],
        main_assemblies=assemblies or [],
        variants=[],
        open_decisions=[],
        zusammenfassung="test concept for physiker char",
        run_id="char-phys-001",
    )


def _ingen(
    source: str,
    lastfaelle: list[LoadCase] | None = None,
    failure_modes: list[FailureMode] | None = None,
    material_hinweise: list[MaterialSpec] | None = None,
) -> IngenieurSpec:
    """Build a minimal IngenieurSpec carrying explicit load cases / failure modes / materials."""
    return IngenieurSpec(
        source_concept=source,
        lastfaelle=lastfaelle or [],
        material_hinweise=material_hinweise or [],
        toleranzen=[],
        failure_modes=failure_modes or [],
        cad_anforderungen=[],
        pruefplan_hinweise=[],
        zusammenfassung="test ingenieur spec for physiker char",
        run_id="char-phys-001",
    )


# --- Facade-killer: two distinct generic inputs must differ -----------------


def test_generic_path_is_input_driven_two_distinct_inputs_differ():
    """FACADE-KILLER: two different non-jetpack inputs must produce different specs.

    The old generic branch ignored `concept` and `ingenieur`, so this assertion
    would have failed (identical output). It now passes only because the path
    derives domains, falsi, budgets etc. from the actual lastfaelle + failure_modes.
    """
    # Input A: tether force load case + tether failure
    lc_a = LoadCase("Tether-Zug", "Max. Zug bei Ausfall", "5 kN Zug", "safety_ladder")
    fm_a = FailureMode("Tether-Überlast", "Tether", "Bruch unter Dynamik", "Lastsensor + Cut", "prior")
    ca = _concept(
        "Ein tethersicherungsgesichertes Fluggerät fuer Tests.",
        [AssemblyConcept("Tragstruktur", "Haelt Pilot und Antrieb", ["Tether-Interface"], "arch")],
    )
    ia = _ingen(ca.source_idea, lastfaelle=[lc_a], failure_modes=[fm_a])

    # Input B: propulsion force load case + different failure
    lc_b = LoadCase("Propulsion-Schub", "Kontrollierter Aufstieg", "2.8 kN Schub", "tech-road")
    fm_b = FailureMode("Motor-Ausfall", "Antrieb", "Kein Schub", "Redundanz-Monitor", "break")
    cb = _concept(
        "Ein schubgetriebenes Inspektionssystem ohne Tether.",
        [AssemblyConcept("Fahr-Prop", "Erzeugt Schub", ["Power-Interface"], "arch-b")],
    )
    ib = _ingen(cb.source_idea, lastfaelle=[lc_b], failure_modes=[fm_b])

    sa = map_to_physiker_spec(ca, ia, run_id="char-a")
    sb = map_to_physiker_spec(cb, ib, run_id="char-b")

    # Distinct inputs -> distinct derived content (names from inputs appear)
    joined_a = " ".join(
        [d.name + " " + d.beschreibung for d in sa.relevante_domaenen]
        + [f.name + " " + f.beschreibung for f in sa.falsifikations_plan]
        + [b.quelle or "" for b in sa.unsicherheits_budget]
    )
    joined_b = " ".join(
        [d.name + " " + d.beschreibung for d in sb.relevante_domaenen]
        + [f.name + " " + f.beschreibung for f in sb.falsifikations_plan]
        + [b.quelle or "" for b in sb.unsicherheits_budget]
    )

    assert sa != sb
    assert joined_a != joined_b

    # Actual input names are consumed and surfaced (no shared constant stub)
    assert "Tether-Zug" in joined_a and "Tether-Überlast" in joined_a
    assert "Propulsion-Schub" in joined_b and "Motor-Ausfall" in joined_b
    assert "Tether-Zug" not in joined_b
    assert "Propulsion-Schub" not in joined_a


def test_lastfaelle_drive_domains_and_falsi_measurands():
    """A load-case's kraft_oder_moment and name flow into domains and falsifikations expected measurand."""
    lc = LoadCase("Rahmen-Zug", "Strukturtest", "1200 N Zugkraft", "dfm")
    c = _concept("Ein lastgetragenes Gestell.", [])
    i = _ingen(c.source_idea, lastfaelle=[lc])
    spec = map_to_physiker_spec(c, i)

    dom_names = " ".join(d.name + d.beschreibung for d in spec.relevante_domaenen)
    falsi_meas = " ".join(p.erwartete_messgroesse for p in spec.falsifikations_plan)
    assert "Kräfte & Dynamik" in dom_names
    assert "Rahmen-Zug" in dom_names
    assert "1200 N Zugkraft" in falsi_meas or "Zugkraft" in falsi_meas


def test_failure_mode_detection_and_name_flow_into_falsi_and_budget():
    """Failure mode name + detection become part of falsi and budget provenance."""
    fm = FailureMode("Sensor-Drift", "Messkopf", "Falsche Werte", "Plausibilitaets-Check", "ing")
    c = _concept("Ein Messgeraet.", [])
    i = _ingen(c.source_idea, failure_modes=[fm])
    spec = map_to_physiker_spec(c, i)

    joined = " ".join(
        f.name + " " + f.beschreibung + " " + (f.erwartete_messgroesse or "")
        for f in spec.falsifikations_plan
    ) + " " + " ".join(b.quelle or "" for b in spec.unsicherheits_budget)
    assert "Sensor-Drift" in joined
    assert "Plausibilitaets-Check" in joined or "Plausibilitaets" in joined


# --- Honest gaps vs. ValueError for signal-free --------------------------------


def test_nonblank_idea_but_no_loads_yields_honest_gaps_not_fabricated_physics():
    """NEGATIVE (partial signal): idea present but no lastfaelle -> explicit Lücken, no F=ma or ±5%."""
    c = _concept("Eine vage mechanische Idee ohne deklarierte Lasten.", [])
    i = _ingen(c.source_idea, lastfaelle=[], failure_modes=[])
    spec = map_to_physiker_spec(c, i)

    # Must produce PhysikerSpec
    assert isinstance(spec, PhysikerSpec)
    assert spec.source_idea == c.source_idea

    # All derived lists use explicit Lücke language; no old canned values
    assert any("Lücke" in d.beschreibung for d in spec.relevante_domaenen)
    assert any("Lücke" in eq.formel for eq in spec.modell_gleichungen)
    assert any("Lücke" in b.wert for b in spec.unsicherheits_budget)
    assert any("Lücke" in p.beschreibung for p in spec.falsifikations_plan)
    # Summary must reflect the idea (even when gaps)
    assert "vage mechanische Idee" in spec.zusammenfassung
    # Must NOT contain the old fabricated constant strings
    assert not any("F = m * a" in eq.formel for eq in spec.modell_gleichungen)
    assert not any("±5%" in b.wert for b in spec.unsicherheits_budget)


@pytest.mark.parametrize(
    "bad_idea",
    ["", "   ", "\t", "\n\n  "],
)
def test_blank_source_idea_and_no_loadcases_raises_valueerror(bad_idea: str):
    """NEGATIVE (no signal): blank source_idea AND zero load cases -> documented ValueError, not stub."""
    c = _concept(bad_idea, [])
    i = _ingen(c.source_idea, lastfaelle=[])
    with pytest.raises(ValueError) as excinfo:
        map_to_physiker_spec(c, i)
    msg = str(excinfo.value).lower()
    assert "blank" in msg or "empty" in msg or "no actionable signal" in msg


def test_materials_with_values_produce_materialphysik_domain():
    """Material hints with numeric values produce a Materialphysik domain (input consumed)."""
    mat = MaterialSpec("Alu-6061", e_modul_gpa=70.0, dichte_kg_m3=2700.0, quelle="werkstoffdaten")
    c = _concept("Eine leichte Struktur.", [])
    i = _ingen(c.source_idea, material_hinweise=[mat])
    spec = map_to_physiker_spec(c, i)
    assert any("Materialphysik" in d.name for d in spec.relevante_domaenen)
    assert any("Alu-6061" in d.beschreibung for d in spec.relevante_domaenen)


# --- Protected regression: jetpack branch byte-stable ---------------------------


def test_jetpack_branch_preserved_verbatim():
    """PROTECTED REGRESSION: the rich jetpack branch must be unchanged (counts + content)."""
    idee = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
    concept = map_to_system_concept(idee, run_id="jet-phys")
    ingen = map_to_ingenieur_spec(concept, run_id="jet-phys")
    phys = map_to_physiker_spec(concept, ingen, run_id="jet-phys")

    # Exact signature counts from the protected jetpack block
    assert len(phys.relevante_domaenen) == 4
    assert len(phys.modell_gleichungen) == 3
    assert len(phys.unsicherheits_budget) == 3
    assert len(phys.falsifikations_plan) == 3

    # Key content strings from the jetpack branch must survive
    dom_names = " ".join(d.name for d in phys.relevante_domaenen)
    assert "Energie & Leistung" in dom_names
    assert "Kräfte & Dynamik" in dom_names
    assert "Schwingungen & Stabilität" in dom_names
    assert "Wärme & Thermik" in dom_names

    eq_forms = " ".join(eq.formel for eq in phys.modell_gleichungen)
    assert "E_in - E_out" in eq_forms
    assert "F_tether = m * a" in eq_forms
    assert "t_open < 3s" in eq_forms

    assert "Jetpack" in phys.zusammenfassung
    assert phys.source_idea == idee
    assert "breakthrough" in (phys.quelle or "").lower() or "ingenieur" in (phys.quelle or "").lower()


# --- Real mappers still produce honest (now input-driven) generic output ---------


def test_existing_generic_idea_still_honest_via_real_mappers():
    """Regression: routing a non-jetpack/non-flug idea through real upstream mappers
    yields a PhysikerSpec whose content derives from the (minimal) ingenieur lastfaelle
    and whose summary reflects the source idea. No more fixed 'F=ma' + '±5%' stub.
    """
    idee = "Ein portables Umweltmessgeraet fuer Feldtests."
    # Ensure it hits generic (no jetpack/flug)
    assert "jetpack" not in idee.lower() and "flug" not in idee.lower()
    concept = map_to_system_concept(idee, run_id="gen-phys")
    ingen = map_to_ingenieur_spec(concept, run_id="gen-phys")
    phys = map_to_physiker_spec(concept, ingen, run_id="gen-phys")

    assert phys.source_idea == idee
    assert len(phys.relevante_domaenen) >= 1
    assert len(phys.falsifikations_plan) >= 1
    # Idea or the generic assembly from architect surfaces in summary
    assert idee.split()[0] in phys.zusammenfassung or "portables" in phys.zusammenfassung.lower()
    # Since ingenieur generic emits one "Grundlast", our derivation must consume it
    joined = " ".join(d.beschreibung for d in phys.relevante_domaenen) + " " + " ".join(
        p.beschreibung for p in phys.falsifikations_plan
    )
    assert "Grundlast" in joined or "Lastfall" in joined
    # Never the old fabricated equation
    assert not any(eq.formel == "F = m * a" for eq in phys.modell_gleichungen)


# --- Property-based invariants --------------------------------------------------


# Safe text: non-empty, no jet/flug substrings (so generic branch is always hit)
_safe = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), min_codepoint=65),
    min_size=4,
    max_size=18,
).filter(lambda s: "jetpack" not in s.lower() and "flug" not in s.lower() and s.strip())


@given(
    lc_names=st.lists(_safe, max_size=3),
    fm_names=st.lists(_safe, max_size=3),
)
def test_property_input_names_surface_in_derived_output(lc_names, fm_names):
    """Invariant: every declared load-case name and failure-mode name appears in the
    derived domains / falsi / budget output (proves consumption, no silent drop or
    cross-contamination from a shared stub). For empty lists we get honest gaps.
    """
    lcs = [LoadCase(name, "Beschreibung des Falls", "Kraft 42 N", "q") for name in lc_names]
    fms = [FailureMode(name, "Baugruppe", "Beschreibung des Fehlers", "Detekt", "q") for name in fm_names]
    c = _concept("Ein generisches lastgetriebenes System ohne schlagwoerter.", [])
    i = _ingen(c.source_idea, lastfaelle=lcs, failure_modes=fms)

    spec = map_to_physiker_spec(c, i)

    joined = " ".join(
        [d.name + " " + d.beschreibung for d in spec.relevante_domaenen]
        + [f.name + " " + f.beschreibung for f in spec.falsifikations_plan]
        + [u.quelle or u.wert for u in spec.unsicherheits_budget]
    )

    if not lc_names and not fm_names:
        # Honest gap path: explicit Lücken, never silence or old canned values
        assert any("Lücke" in d.beschreibung for d in spec.relevante_domaenen)
        assert any("Lücke" in eq.formel for eq in spec.modell_gleichungen)
        return

    for name in lc_names + fm_names:
        assert name in joined, f"Name {name} from input must appear in derived output"


@given(st.text(min_size=1).filter(lambda s: s.strip() and "jetpack" not in s.lower() and "flug" not in s.lower()))
def test_property_summary_always_reflects_source_idea(idea: str):
    """For any non-blank non-jetpack idea (even when ingenieur carries only its default load),
    the summary must contain (a fragment of) the source idea.
    """
    c = map_to_system_concept(idea)
    i = map_to_ingenieur_spec(c)
    spec = map_to_physiker_spec(c, i)
    # The summary is built from the real source_idea
    assert idea.strip()[:12] in spec.zusammenfassung or any(tok in spec.zusammenfassung for tok in idea.strip().split()[:2])
