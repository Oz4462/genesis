"""Characterization tests for boundary_reviser.revise_boundary (T02 depth-audit).

These tests fail loudly if revise_boundary is a facade:
- It only revised boundaries whose EXACT German key strings were hardcoded (jetpack-only).
- The generic else always fabricated a BoundaryRevision even when no frontier item
  addressed anything ("generische Machbarkeit der Idee" + "to be re-evaluated").

The headline claim ("aktualisiert die Grenze, wenn neue Evidenz auftaucht") must now
be true for any input: revision is evidence-driven (content/relevanz match), emits
a revision ONLY when an item genuinely addresses a boundary/gap, and returns an
honest no-op (zero revisions, map substantively unchanged) otherwise.

Every test uses real upstream constructors (map_development_front, watch_frontier,
DevelopmentFrontMap, FrontierItem/Update). The unit under test is never mocked.

Protected: the rich jetpack descriptive path still yields the detailed ladder step
and augmented heutige_grenze (L3 seam completeness).

Includes property-based test (hypothesis) for the "no fabricated revision" + "run_id
propagation" + "never more revisions than addressable items" invariants.

Run:
  PYTHONPATH=src python -m pytest tests/test_boundary_reviser_characterization.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.grenzverschiebung.boundary_reviser import (  # noqa: E402
    BoundaryRevision,
    RevisedFrontMap,
    revise_boundary,
)
from gen.grenzverschiebung.breakthrough_watch import (  # noqa: E402
    FrontierItem,
    FrontierUpdate,
    watch_frontier,
)
from gen.grenzverschiebung.development_front import (  # noqa: E402
    DevelopmentFrontMap,
    Grenztyp,
    map_development_front,
)


_JETPACK = "Ich will ein Jetpack bauen, das Menschen sicher über einer Menge frei fliegen lässt."
_GENERIC = "Ein tragbares Gerät, das Schwerkraft lokal aufhebt."


def _front(idee: str, run_id: str | None = None) -> DevelopmentFrontMap:
    return map_development_front(idee, run_id=run_id)


def _frontier(front: DevelopmentFrontMap, run_id: str | None = None) -> FrontierUpdate:
    return watch_frontier(front, run_id=run_id)


# --- Protected jetpack regression (rich descriptive path + real revisions) ---

def test_jetpack_produces_detailed_revisions_and_ladder_step():
    """The rich jetpack path (used by downstream safety_ladder etc.) must survive unchanged
    in its observable detailed outputs while the revision decision itself is now generic.
    """
    front = _front(_JETPACK, "r-jet-1")
    frontier = _frontier(front, "r-jet-1")
    rev = revise_boundary(front, frontier, run_id="r-jet-1")

    assert isinstance(rev, RevisedFrontMap)
    assert rev.source_traum == _JETPACK
    assert rev.run_id == "r-jet-1"
    assert rev.revised_map.run_id == "r-jet-1"

    # At least the two energy/control/recovery driven revisions (evidence match)
    assert len(rev.revisions) >= 2
    changed = {r.changed_boundary for r in rev.revisions}
    assert any("Energie" in c or "portable" in c.lower() for c in changed)
    assert any("Failure" in c or "Recovery" in c or "bemannter" in c.lower() for c in changed)

    # All grenzen values must be real enums (no str pollution from old code)
    assert all(isinstance(v, Grenztyp) for v in rev.revised_map.grenzen.values())

    # Rich descriptive augmentation still present (protected regression)
    assert "REVISED" in rev.revised_map.heutige_grenze
    assert any("Neue Evidenz aus FrontierUpdate" in s.beschreibung for s in rev.revised_map.experimentleiter)

    # Revisions carry the item's echte quelle (provenance)
    assert any(r.quelle and "GENESIS" in (r.quelle or "") or "technology" in (r.quelle or "").lower()
               for r in rev.revisions)


# --- Honest no-op / no fabricated revision (core facade killer) ---

def test_generic_non_matching_frontier_yields_zero_revisions_honest_noop():
    """Generic idea + its default generic frontier item (relevanz does not address the
    single generic grenzen key) must produce ZERO revisions and leave the map substantively
    unchanged. This is the opposite of the old unconditional fabrication.
    """
    front = _front(_GENERIC, "r-gen-1")
    frontier = _frontier(front, "r-gen-1")  # generic "Allgemeine Technologie..." item
    rev = revise_boundary(front, frontier, run_id="r-gen-1")

    assert len(rev.revisions) == 0
    assert "No boundary revision emitted" in rev.zusammenfassung
    assert "honest no-op" in rev.zusammenfassung

    # Substantive content unchanged (grenzen + heutige are equal)
    assert rev.revised_map.grenzen == front.grenzen
    assert rev.revised_map.heutige_grenze == front.heutige_grenze

    # Never the old fabricated strings
    assert not any("generische" in r.changed_boundary.lower() for r in rev.revisions)
    assert not any("to be re-evaluated" in (r.new_typ or "").lower() for r in rev.revisions)

    # run_id propagated even on no-op
    assert rev.revised_map.run_id == "r-gen-1"


def test_empty_items_is_honest_noop():
    front = _front(_GENERIC, "r-empty")
    upd = FrontierUpdate(source_traum=front.traum, items=[], zusammenfassung="none", run_id="r-empty")
    rev = revise_boundary(front, upd, run_id="r-empty")

    assert rev.revisions == []
    assert rev.revised_map.grenzen == front.grenzen
    assert rev.revised_map.run_id == "r-empty"


# --- Evidence-driven: real match from item content/relevanz produces revision + quelle ---

def test_item_content_match_produces_revision_with_item_quelle():
    """A crafted frontier item whose relevanz_fuer_gap + titel match a grenzen key
    must cause exactly one BoundaryRevision carrying the item's source (quelle).
    """
    # A minimal front with one addressable boundary (use real ctor)
    front = DevelopmentFrontMap(
        traum="Custom energy gap idea",
        heutige_grenze="Baseline boundary",
        fehlende_faehigkeiten=["High energy density gap"],
        experimentleiter=[],
        grenzen={"portable high-density energy for hover payload": Grenztyp.NEEDS_BREAKTHROUGH},
        abbruchkriterien=[],
        naechste_stufe="later",
        run_id="r-match-1",
        quelle="test",
    )
    item = FrontierItem(
        titel="Solid-State Battery Breakthrough (2026 Lab Results)",
        typ="Material",
        beschreibung="Sulfide cells >350 Wh/kg",
        relevanz_fuer_gap="Energie-Dichte P1",
        moeglicher_impact="Solves portable storage",
        quelle="https://example.test/solid-2026",
    )
    upd = FrontierUpdate(source_traum=front.traum, items=[item], zusammenfassung="one match", run_id="r-match-1")

    rev = revise_boundary(front, upd, run_id="r-match-1")

    assert len(rev.revisions) == 1
    r = rev.revisions[0]
    assert "energy" in r.changed_boundary.lower() or "portable" in r.changed_boundary.lower()
    assert r.quelle == "https://example.test/solid-2026"
    assert r.old_typ == Grenztyp.NEEDS_BREAKTHROUGH.value
    assert r.new_typ in (Grenztyp.POSSIBLE_BUT_UNSAFE_DIRECTLY.value, Grenztyp.KNOWN_POSSIBLE.value)

    # The revised_map actually has the downgraded type (input-derived)
    new_val = rev.revised_map.grenzen[r.changed_boundary]
    assert isinstance(new_val, Grenztyp)
    assert new_val != Grenztyp.NEEDS_BREAKTHROUGH

    # Original front not mutated (important for determinism in callers)
    assert front.grenzen["portable high-density energy for hover payload"] == Grenztyp.NEEDS_BREAKTHROUGH


# --- Input sensitivity: changing the driving frontier changes output meaningfully ---

def test_output_changes_when_frontier_items_change():
    """Proves the frontier_update (the driving evidence) is actually consumed, not ignored."""
    front = _front(_JETPACK, "r-sens-1")

    # Full jetpack frontier (3 addressing items)
    f_full = _frontier(front, "r-sens-1")
    r_full = revise_boundary(front, f_full, run_id="r-sens-1")

    # Minimal frontier containing only an energy-addressing item
    item_only_e = FrontierItem(
        titel="Solid-State Battery Breakthrough (2026 Lab Results)",
        typ="Material",
        beschreibung="...",
        relevanz_fuer_gap="Energie-Dichte P1",
        moeglicher_impact="...",
        quelle="q-e",
    )
    f_e = FrontierUpdate(source_traum=front.traum, items=[item_only_e], zusammenfassung="e-only", run_id="r-sens-1")
    r_e = revise_boundary(front, f_e, run_id="r-sens-1")

    # Meaningful difference: fewer revisions (or different set) when input frontier is smaller
    assert len(r_e.revisions) < len(r_full.revisions) or \
           {rr.changed_boundary for rr in r_e.revisions} != {rr.changed_boundary for rr in r_full.revisions}

    # The energy boundary appears in both (it is addressed by the common item)
    assert any("Energie" in rr.changed_boundary or "portable" in rr.changed_boundary.lower()
               for rr in r_e.revisions)


# --- Property-based invariants (no fabrication, determinism properties, bounds) ---

@given(
    st.lists(
        st.builds(
            FrontierItem,
            titel=st.text(min_size=3, max_size=40).filter(lambda s: s.strip()),
            typ=st.sampled_from(["Paper", "Material", "Tool", "Verfahren"]),
            beschreibung=st.text(min_size=0, max_size=30),
            relevanz_fuer_gap=st.text(min_size=3, max_size=20),
            moeglicher_impact=st.text(min_size=0, max_size=20),
            quelle=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
        ),
        min_size=0,
        max_size=6,
    )
)
@settings(max_examples=30, deadline=400)
def test_property_no_fabricated_revisions_and_bounds(items: list[FrontierItem]):
    """For arbitrary frontier items against a generic front:
    - never emit the old fabricated revision strings
    - #revisions <= #items (and <= #grenzen keys)
    - run_id always propagated to both wrapper and inner map
    - always a valid RevisedFrontMap with DevelopmentFrontMap inside
    """
    front = _front(_GENERIC, "hyp-r")
    upd = FrontierUpdate(
        source_traum=front.traum,
        items=items,
        zusammenfassung="hyp",
        run_id="hyp-r",
    )
    rev = revise_boundary(front, upd, run_id="hyp-r")

    assert isinstance(rev, RevisedFrontMap)
    assert isinstance(rev.revised_map, DevelopmentFrontMap)
    assert rev.run_id == "hyp-r"
    assert rev.revised_map.run_id == "hyp-r"

    assert len(rev.revisions) <= len(items)
    assert len(rev.revisions) <= len(front.grenzen)

    for r in rev.revisions:
        assert "generische" not in r.changed_boundary.lower()
        assert "to be re-evaluated" not in (r.new_typ or "").lower()
        assert isinstance(r, BoundaryRevision)

    # grenzen values remain proper enums
    assert all(isinstance(v, Grenztyp) for v in rev.revised_map.grenzen.values())


def test_revised_map_uses_real_constructor_and_propagates_run_id():
    """Sanity: reconstruction always goes through DevelopmentFrontMap (visible by fields)."""
    front = _front(_JETPACK, "r-ctor")
    frontier = _frontier(front, "r-ctor")
    rev = revise_boundary(front, frontier, run_id="r-ctor-42")

    m = rev.revised_map
    # These fields exist only because the canonical dataclass was used
    assert hasattr(m, "traum")
    assert hasattr(m, "grenzen")
    assert m.run_id == "r-ctor-42"
