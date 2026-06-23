"""Characterization tests for architekt.map_to_system_concept.

These tests pin down the facade-killer contract (PLAN T04):
- the generic (non-jetpack) path must genuinely reflect the `idea` text, so two
  distinct ideas yield distinguishable SystemConcepts (the old `else` branch
  returned a fixed stub independent of input — a facade);
- an empty/whitespace idea must raise ValueError (no fabricated stub for a non-input);
- the rich jetpack branch is preserved verbatim as a protected regression;
- open_decisions still honestly mark the missing full analysis.
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from gen.pipelines.architekt import (
    SystemConcept,
    map_to_system_concept,
)


def _concat_text(concept: SystemConcept) -> str:
    """All free text of a concept, for substring/equality assertions."""
    parts = [concept.zusammenfassung]
    parts.extend(r.text for r in concept.requirements)
    parts.extend(a.purpose for a in concept.main_assemblies)
    parts.extend(concept.open_decisions)
    return "\n".join(parts)


# --- Facade-killer: two distinct generic ideas must differ -----------------


def test_generic_two_distinct_ideas_differ() -> None:
    """The original facade returned an identical stub for any non-jetpack idea.

    Two clearly different ideas must now produce distinguishable concepts.
    """
    a = map_to_system_concept("a quiet desk lamp")
    b = map_to_system_concept("a hydroponic garden tower")

    assert a != b
    # The driving difference must show up in the actual content, not just source_idea.
    assert _concat_text(a) != _concat_text(b)


def test_generic_idea_text_surfaces_in_requirements_and_summary() -> None:
    """The idea string itself must be consumed into the derived fields."""
    idea = "a solar-powered water purifier"
    concept = map_to_system_concept(idea)

    assert idea in _concat_text(concept)
    # Specifically: it surfaces in a requirement AND the summary (not only source_idea).
    assert any(idea in r.text for r in concept.requirements)
    assert idea in concept.zusammenfassung


def test_generic_open_decisions_stay_honest() -> None:
    """Honest abstention: the generic path must still flag the missing full analysis."""
    concept = map_to_system_concept("a modular bookshelf")
    joined = " ".join(concept.open_decisions).lower()
    assert "needs full" in joined or "noch nicht" in joined


# --- Negative path: no fabricated stub for a non-input ---------------------


@pytest.mark.parametrize("bad", ["", "   ", "\t", "\n  \n"])
def test_empty_or_whitespace_idea_raises(bad: str) -> None:
    with pytest.raises(ValueError):
        map_to_system_concept(bad)


# --- Protected regression: jetpack branch unchanged ------------------------


def test_jetpack_branch_preserved() -> None:
    """The rich jetpack concept must keep its detailed structure verbatim."""
    concept = map_to_system_concept("ein Jetpack für einen Menschen")

    assert len(concept.requirements) == 4
    assert len(concept.main_assemblies) == 5
    assert len(concept.variants) == 6
    assert len(concept.open_decisions) == 3
    # A signature line of the jetpack summary must be intact.
    assert "5 Hauptbaugruppen" in concept.zusammenfassung
    # The "mensch + fliegen" trigger reaches the same rich branch.
    rich = map_to_system_concept("ein Mensch will fliegen")
    assert len(rich.main_assemblies) == 5


def test_jetpack_and_generic_are_distinguishable() -> None:
    """A jetpack idea and a generic idea must not collapse to the same concept."""
    jet = map_to_system_concept("jetpack")
    generic = map_to_system_concept("a teapot")
    assert len(jet.main_assemblies) > len(generic.main_assemblies)


# --- Invariant (property-based): non-blank idea -> consumed & well-formed ---


@given(st.text(min_size=1).filter(lambda s: s.strip() and "jetpack" not in s.lower()))
def test_property_generic_consumes_idea(idea: str) -> None:
    """For any non-blank, non-jetpack idea, the stripped text is surfaced and the
    concept is honest and well-formed (no silent constant stub)."""
    concept = map_to_system_concept(idea)

    assert concept.source_idea == idea
    assert idea.strip() in _concat_text(concept)
    assert concept.requirements  # never empty
    assert concept.main_assemblies
    # Honest abstention preserved for every generic idea.
    assert any(
        "needs full" in d.lower() or "noch nicht" in d.lower()
        for d in concept.open_decisions
    )


@given(st.text().filter(lambda s: not s.strip()))
def test_property_blank_idea_always_raises(blank: str) -> None:
    with pytest.raises(ValueError):
        map_to_system_concept(blank)
