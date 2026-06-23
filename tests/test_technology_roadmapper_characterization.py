"""Characterization tests for technology_roadmapper (T02).

Proves that the generic branch of build_technology_roadmap now derives
TechnologyGap entries from the *actual* stand_plan.stands (TestStandSpec)
instead of emitting a single fixed canned gap (former facade).

- Facade detectors: different stands -> observably different roadmap; empty -> honest empty.
- Jetpack rich branch preserved verbatim as protected regression (L3 seam).
- Property-based tests with Hypothesis for the cardinality + referenz invariant.
- All inputs built via real TestStandPlan/TestStandSpec constructors.
- Negative/empty case + determinism covered.
- Does not edit the legacy test_technology_roadmapper.py.

See docs/audit/DEPTH_AUDIT_technology_roadmapper.md and GENESIS_PLATFORM_PLAN.md §3.3.
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from gen.grenzverschiebung.technology_roadmapper import (
    TechnologyGap,
    TechnologyRoadmap,
    build_technology_roadmap,
)
from gen.grenzverschiebung.teststand_architect import (
    TestStandPlan,
    TestStandSpec,
)


# --- Helpers: construct via REAL public constructors (never invent fields) ---


def _spec(
    *,
    name: str = "T0 — Generic Validation Rig",
    beschreibung: str = "Bench setup for frontier validation.",
    sicherheitsmassnahmen: list[str] | None = None,
    messungen: list[str] | None = None,
    dauer_aufwand: str = "1–2 Wochen",
    quelle: str | None = "test",
) -> TestStandSpec:
    return TestStandSpec(
        name=name,
        beschreibung=beschreibung,
        sicherheitsmassnahmen=sicherheitsmassnahmen or ["Keine bemannte Phase"],
        messungen=messungen or ["Abdeckung der Grenzen"],
        dauer_aufwand=dauer_aufwand,
        quelle=quelle,
    )


def _plan(
    *specs: TestStandSpec,
    traum: str = "Generische Idee ohne jetpack oder menschliches Fliegen",
    run_id: str | None = "road-char-001",
) -> TestStandPlan:
    """Build a TestStandPlan using only real constructors."""
    return TestStandPlan(
        source_traum=traum,
        stands=list(specs),
        zusammenfassung="test stand plan",
        run_id=run_id,
        quelle="test",
    )


# --- Facade detectors (must fail on old constant generic implementation) ---


def test_generic_derives_gaps_from_stands_input_is_consumed():
    """L2: two different stand lists on same non-jetpack traum produce different roadmaps."""
    s1 = _spec(name="T-A", messungen=["Messung A"], sicherheitsmassnahmen=["S-A"])
    s2 = _spec(name="T-B", messungen=["Messung B"], sicherheitsmassnahmen=["S-B"])
    p1 = _plan(s1, traum="Tragbares Anti-Schwerkraft-Gerät")
    p2 = _plan(s2, traum="Tragbares Anti-Schwerkraft-Gerät")

    r1 = build_technology_roadmap(p1)
    r2 = build_technology_roadmap(p2)

    # Output changes when driving input (stands) changes.
    assert r1 != r2
    assert len(r1.gaps) == 1
    assert len(r2.gaps) == 1
    assert r1.gaps[0].gap_referenz == "T-A"
    assert r2.gaps[0].gap_referenz == "T-B"
    # beschreibung must reflect the stand content (computed, not canned).
    assert "Messung A" in r1.gaps[0].beschreibung
    assert "Messung B" in r2.gaps[0].beschreibung
    assert "S-A" in r1.gaps[0].beschreibung or "S-A" in r1.gaps[0].abhaengigkeiten


def test_one_gap_per_stand_and_gap_referenz_points_at_stand_name():
    """L1/L2: cardinality and referenz exactly follow the stands list."""
    specs = [
        _spec(name="TX-1", messungen=["m1", "m2"]),
        _spec(name="TX-2", messungen=["m3"]),
        _spec(name="TX-3", messungen=["m4"], sicherheitsmassnahmen=["safe-1"]),
    ]
    # traum must not contain "jetpack" or ("mensch" and "fliegen") substrings, else jetpack branch is taken
    plan = _plan(*specs, traum="Tragbares Gravitationsaufhebungs-Geraet fuer Testzwecke")
    roadmap = build_technology_roadmap(plan, run_id="rid-x")

    assert len(roadmap.gaps) == 3
    refs = [g.gap_referenz for g in roadmap.gaps]
    assert refs == ["TX-1", "TX-2", "TX-3"]
    # run_id and source_traum propagated
    assert roadmap.run_id == "rid-x"
    assert roadmap.source_traum == plan.source_traum
    # abhaengigkeiten reflect safety when present
    assert "safe-1" in roadmap.gaps[2].abhaengigkeiten


def test_empty_stands_yields_honest_empty_gaps_and_explicit_summary():
    """L4 + negative: empty stands -> gaps==[], summary explicitly states no stands (no fabricated gap)."""
    plan = _plan(traum="Vollkommen neue Idee ohne jeden Stand")
    # Force empty after construction (realistic signal-free input)
    empty_plan = TestStandPlan(
        source_traum=plan.source_traum,
        stands=[],
        zusammenfassung=plan.zusammenfassung,
        run_id="empty-42",
        quelle=plan.quelle,
    )
    # run_id is supplied via the kwarg (the function does not auto-take it from the plan object)
    roadmap = build_technology_roadmap(empty_plan, run_id="empty-42")

    assert roadmap.gaps == []
    assert roadmap.run_id == "empty-42"
    # Explicit abstention language per spec (no "Grundlegende..." canned item).
    summary_lower = roadmap.zusammenfassung.lower()
    assert "keine prüfstände" in summary_lower or "no stands" in summary_lower or "keine" in summary_lower
    assert "keine" in summary_lower  # at minimum the honest marker


# --- Protected jetpack regression (L3) ---


def test_jetpack_branch_still_returns_exact_rich_gaps_verbatim():
    """L3: jetpack traum produces the original 3 detailed gaps, unaffected by stands content."""
    # Provide stands that would be different; branch must ignore them and stay verbatim.
    custom_stands = [
        _spec(name="T-Custom-Should-Be-Ignored", messungen=["should not appear"]),
    ]
    plan = _plan(
        *custom_stands,
        traum="Ich will ein Jetpack bauen, das Menschen sicher fliegen lässt.",
        run_id="jp-reg-007",
    )
    roadmap = build_technology_roadmap(plan)

    assert len(roadmap.gaps) == 3
    names = [g.name for g in roadmap.gaps]
    assert "Hochdichte portable Energie (Li-Metal / Solid-State / Wasserstoff)" in names
    assert "Leichte, zuverlässige Redundante Flugkontrolle für bemannte VTOL" in names
    assert "Schnelle, leichte, zuverlässige bemannte Notfall-Recovery-Systeme" in names
    # The original canned referenzen stay for jetpack (verbatim)
    refs = [g.gap_referenz for g in roadmap.gaps]
    assert "capability_gap MISSING_TECHNOLOGY + milestone M1 + teststand T1" in refs
    assert roadmap.source_traum == plan.source_traum


def test_jetpack_gaps_unchanged_even_with_zero_stands():
    """Jetpack rich output unchanged when stands=[] (branch decision on traum only)."""
    plan = TestStandPlan(
        source_traum="mensch kann mit diesem jetpack fliegen",
        stands=[],
        zusammenfassung="empty for jetpack traum",
        run_id=None,
    )
    roadmap = build_technology_roadmap(plan)
    assert len(roadmap.gaps) == 3
    assert any("Energie" in g.name for g in roadmap.gaps)


# --- Determinism + provenance ---


def test_determinism_same_plan_same_roadmap():
    """A5 contract: identical input plan yields identical roadmap."""
    p = _plan(_spec(name="D1"), _spec(name="D2"), traum="Determinismus Test")
    r1 = build_technology_roadmap(p, run_id="det-1")
    r2 = build_technology_roadmap(p, run_id="det-1")
    assert r1 == r2
    assert r1.gaps == r2.gaps


def test_run_id_override_is_used():
    p = _plan(_spec(name="R1"))
    r = build_technology_roadmap(p, run_id="override-99")
    assert r.run_id == "override-99"


# --- Fail-loud / type edge (real public API behavior) ---


def test_none_stand_plan_raises():
    """Negative: None input fails loud (no silent default roadmap)."""
    with pytest.raises((TypeError, AttributeError)):
        build_technology_roadmap(None)  # type: ignore[arg-type]


# --- Property-based tests (Hypothesis) for invariants ---


@given(
    names=st.lists(
        st.text(min_size=3, max_size=50).filter(lambda s: s.strip() and "jetpack" not in s.lower() and "fliegen" not in s.lower()),
        min_size=0,
        max_size=5,
        unique=True,
    )
)
def test_property_generic_gap_count_equals_stand_count_and_referenz_match(names: list[str]):
    """Invariant: for any list of non-jetpack stand names, #gaps == #stands and every gap_referenz comes from the input names.
    Empty list produces empty gaps (honest abstention).
    """
    specs = [
        _spec(
            name=n,
            messungen=[f"mess-{i}" for i, _ in enumerate(n)],
            sicherheitsmassnahmen=["s-" + n[:3]] if n else [],
        )
        for n in names
    ]
    plan = _plan(*specs, traum="Property test generische Idee ohne Flugbegriffe")
    roadmap = build_technology_roadmap(plan)

    if not names:
        assert roadmap.gaps == []
        assert "keine" in roadmap.zusammenfassung.lower()
    else:
        assert len(roadmap.gaps) == len(names)
        input_names = set(names)
        for g in roadmap.gaps:
            assert g.gap_referenz in input_names, f"gap_referenz {g.gap_referenz!r} not from input stands"
        # All input stands are represented (1:1 completeness).
        produced = {g.gap_referenz for g in roadmap.gaps}
        assert produced == input_names


@given(
    n_stands=st.integers(min_value=1, max_value=4),
)
def test_property_different_stand_count_changes_gap_count(n_stands: int):
    """Changing the number of stands changes the number of gaps (input drives cardinality)."""
    specs = [_spec(name=f"PS-{i}") for i in range(n_stands)]
    plan = _plan(*specs, traum="Kardinalitäts-Invariante")
    roadmap = build_technology_roadmap(plan)
    assert len(roadmap.gaps) == n_stands
