"""Characterization / facade-detection tests for src/gen/clarification.py.

Goal (depth audit, per the team's facade-killer rule): prove that clarification is
GENUINELY measurand-driven against the real RECIPES, not a canned constant —
(a) the question set changes meaningfully when a driving measurand is added/removed
(the input is actually consumed), and (b) the documented honest-abstention path fires
(physics-free / fully-specified specs ask nothing). All specs are built through the
REAL core.state constructors and the REAL physics_selection.RECIPES.

Run:  pytest tests/test_clarification_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from hypothesis import given, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.clarification import (  # noqa: E402
    ClarifyingQuestion,
    apply_answers,
    clarifying_questions,
    is_underspecified,
)
from gen.core.state import Quantity, Specification, ValueOrigin  # noqa: E402
from gen.physics_selection import RECIPES  # noqa: E402


def _q(qid: str, measurand: str, unit: str = "1") -> Quantity:
    """A minimal declared quantity carrying `measurand` — clarification keys only on
    the measurand tag, so value/unit are immaterial to detection (still real, finite)."""
    return Quantity(id=qid, name=qid, value=1.0, unit=unit,
                    origin=ValueOrigin.DECISION, rationale="test", measurand=measurand)


def _spec(quantities) -> Specification:
    return Specification(run_id="r", idea="x", quantities=quantities)


# --- recipe anchors: read straight from the REAL catalog so the test tracks the source ---
_SHAFT = next(r for r in RECIPES if r.trigger == "shaft.torque")
_BUCKLING = next(r for r in RECIPES if r.trigger == "column.axial_load")
_VESSEL = next(r for r in RECIPES if r.trigger == "vessel.pressure")


def _measurands(recipe) -> set[str]:
    return {m for (m, _unit) in recipe.inputs.values()}


# ---------------------------------------------------------------------------
# (1) one missing input of an INDICATED recipe -> exactly one targeted question
# ---------------------------------------------------------------------------

def test_single_missing_input_yields_exactly_that_question() -> None:
    """A spec with the shaft-torsion TRIGGER and every input but ONE produces exactly one
    ClarifyingQuestion, for the missing measurand, priority 1, unblocking that one check."""
    missing = "material.shear_strength"
    present = _measurands(_SHAFT) - {missing}
    assert missing in _measurands(_SHAFT)  # guard: the anchor is really an input

    spec = _spec([_q(f"q{i}", m) for i, m in enumerate(sorted(present))])
    questions = clarifying_questions(spec)

    assert len(questions) == 1
    only = questions[0]
    assert isinstance(only, ClarifyingQuestion)
    assert only.measurand == missing
    # priority == number of INDICATED checks needing it (here just shaft torsion)
    assert only.priority == 1
    # it ALONE makes shaft torsion runnable -> appears in unblocks
    assert only.unblocks == (_SHAFT.name,)
    assert is_underspecified(spec) is True


def test_priority_counts_indicated_checks_and_unblocks_lists_them() -> None:
    """A measurand needed by TWO indicated checks (buckling + pressure vessel both miss only
    material.yield_strength) is asked ONCE with priority 2 and unblocks BOTH checks — proving
    priority is the EVPI count and unblocks is the sole-missing-input set, not a constant."""
    shared = "material.yield_strength"
    assert shared in _measurands(_BUCKLING) and shared in _measurands(_VESSEL)

    present = (_measurands(_BUCKLING) | _measurands(_VESSEL)) - {shared}
    spec = _spec([_q(f"q{i}", m) for i, m in enumerate(sorted(present))])
    questions = clarifying_questions(spec)

    assert len(questions) == 1
    only = questions[0]
    assert only.measurand == shared
    assert only.priority == 2  # two indicated checks need it
    assert only.unblocks == tuple(sorted((_BUCKLING.name, _VESSEL.name)))


def test_questions_sorted_by_descending_priority_then_measurand() -> None:
    """With several missing inputs the list is ordered (-priority, measurand) deterministically —
    the high-value question ranks first."""
    # buckling + vessel indicated, yield_strength shared (prio 2), every other input missing (prio 1).
    spec = _spec([_q("a", "column.axial_load"), _q("p", "vessel.pressure")])
    questions = clarifying_questions(spec)

    keys = [(-q.priority, q.measurand) for q in questions]
    assert keys == sorted(keys)
    assert questions[0].measurand == "material.yield_strength"
    assert questions[0].priority == 2


# ---------------------------------------------------------------------------
# (2) adding/removing a present measurand changes the question set (input consumed)
# ---------------------------------------------------------------------------

def test_adding_the_missing_measurand_removes_its_question() -> None:
    """Declaring the one missing input flips the spec from one question to zero — the question
    set is a function of the present measurands, not a canned output."""
    missing = "material.shear_strength"
    base_present = _measurands(_SHAFT) - {missing}

    underspecified = _spec([_q(f"q{i}", m) for i, m in enumerate(sorted(base_present))])
    complete = _spec(underspecified.quantities + [_q("filled", missing)])

    before = clarifying_questions(underspecified)
    after = clarifying_questions(complete)

    assert [q.measurand for q in before] == [missing]
    assert after == []
    assert before != after  # the driving input genuinely changed the result


def test_removing_an_input_changes_which_checks_an_answer_unblocks() -> None:
    """Dropping a second input of buckling means yield_strength no longer ALONE unblocks
    buckling (two inputs now missing) — its `unblocks` shrinks to just the pressure vessel.
    Proves `unblocks` tracks the actual present set, not a fixed label."""
    shared = "material.yield_strength"
    full = (_measurands(_BUCKLING) | _measurands(_VESSEL)) - {shared}

    spec_all = _spec([_q(f"q{i}", m) for i, m in enumerate(sorted(full))])
    q_all = next(q for q in clarifying_questions(spec_all) if q.measurand == shared)
    assert set(q_all.unblocks) == {_BUCKLING.name, _VESSEL.name}

    # remove one NON-TRIGGER buckling-only input -> buckling STAYS indicated (its trigger is still
    # present) but now misses TWO inputs -> shared no longer ALONE unblocks it. Excluding the
    # trigger is essential: dropping it would de-indicate buckling entirely and exercise a
    # different (trigger-absent) path than the sole-unblock-shrinks path this test documents.
    buckling_only = sorted(_measurands(_BUCKLING) - _measurands(_VESSEL) - {shared})
    dropped = next(m for m in buckling_only if m != _BUCKLING.trigger)
    spec_dropped = _spec([q for q in spec_all.quantities if q.measurand != dropped])
    assert _BUCKLING.trigger in {q.measurand for q in spec_dropped.quantities}  # still indicated
    q_dropped = next(q for q in clarifying_questions(spec_dropped) if q.measurand == shared)
    assert set(q_dropped.unblocks) == {_VESSEL.name}
    assert q_dropped.unblocks != q_all.unblocks


# ---------------------------------------------------------------------------
# (3) honest abstention — physics-free AND fully-specified ask nothing (negative case)
# ---------------------------------------------------------------------------

def test_physics_free_spec_asks_nothing() -> None:
    """A spec whose measurands trigger no recipe is NOT interrogated — empty list, not underspecified."""
    spec = _spec([_q("w", "geometry.width"), _q("c", "color.hue")])
    assert clarifying_questions(spec) == []
    assert is_underspecified(spec) is False


def test_empty_spec_asks_nothing() -> None:
    """No quantities at all -> no indicated physics -> nothing to clarify."""
    spec = _spec([])
    assert clarifying_questions(spec) == []
    assert is_underspecified(spec) is False


def test_fully_specified_spec_asks_nothing() -> None:
    """Every input of an indicated recipe present -> no gap -> honest empty list."""
    spec = _spec([_q(f"q{i}", m) for i, m in enumerate(sorted(_measurands(_SHAFT)))])
    assert clarifying_questions(spec) == []
    assert is_underspecified(spec) is False


# ---------------------------------------------------------------------------
# (4) apply_answers — adds only-new, stable id, DECISION origin, no overwrite, no mutation
# ---------------------------------------------------------------------------

def test_apply_answers_adds_only_new_measurands_immutably() -> None:
    existing = _q("orig", "material.yield_strength", unit="MPa")
    existing_value = existing.value
    spec = _spec([existing])

    new_spec = apply_answers(spec, {
        "material.yield_strength": (999.0, "MPa"),     # already declared -> must NOT be added/overwritten
        "material.shear_strength": (180.0, "MPa"),     # new -> added
    })

    # original spec untouched (new object returned)
    assert new_spec is not spec
    assert len(spec.quantities) == 1
    assert spec.quantities[0] is existing and existing.value == existing_value

    added = [q for q in new_spec.quantities if q.id not in {"orig"}]
    assert len(added) == 1
    q = added[0]
    assert q.measurand == "material.shear_strength"
    assert q.id == "q_clarified_material_shear_strength"  # stable, measurand-derived
    assert q.origin is ValueOrigin.DECISION
    assert q.value == 180.0 and q.unit == "MPa"

    # the pre-existing declaration kept its original value (no silent overwrite)
    kept = next(q for q in new_spec.quantities if q.measurand == "material.yield_strength")
    assert kept.value == existing_value


def test_apply_answers_empty_is_identity_in_content() -> None:
    spec = _spec([_q("a", "shaft.torque")])
    out = apply_answers(spec, {})
    assert out is not spec
    assert [q.measurand for q in out.quantities] == ["shaft.torque"]


# ---------------------------------------------------------------------------
# property-based invariants (round-trip / idempotency / id stability)
# ---------------------------------------------------------------------------

# A pool of valid recipe measurands so generated ids stay identifier-safe.
_POOL = sorted({m for r in RECIPES for (m, _u) in r.inputs.values()})


@given(
    chosen=st.lists(st.sampled_from(_POOL), unique=True, min_size=0, max_size=6),
    value=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_apply_answers_invariants(chosen, value) -> None:
    """For any set of fresh measurands, apply_answers adds exactly them, each with the
    documented stable id / DECISION origin, never mutates the input, and is IDEMPOTENT
    (re-applying the same answers — now already present — adds nothing more)."""
    spec = _spec([])
    answers = {m: (value, "1") for m in chosen}

    once = apply_answers(spec, answers)
    assert spec.quantities == []  # input never mutated

    added = {q.measurand: q for q in once.quantities}
    assert set(added) == set(chosen)
    for m, q in added.items():
        assert q.id == f"q_clarified_{m.replace('.', '_')}"
        assert q.origin is ValueOrigin.DECISION
        assert q.value == value

    # idempotency: a second application sees them already declared -> no growth, same ids
    twice = apply_answers(once, answers)
    assert {q.id for q in twice.quantities} == {q.id for q in once.quantities}
    assert len(twice.quantities) == len(once.quantities)


@given(present=st.lists(st.sampled_from(_POOL), unique=True, min_size=0, max_size=8))
def test_clarifying_questions_deterministic_and_sorted(present) -> None:
    """The questions are a deterministic, correctly-ordered function of the present measurands;
    no triggered question targets an already-present measurand (it asks only for what is MISSING)."""
    spec = _spec([_q(f"q{i}", m) for i, m in enumerate(present)])
    a = clarifying_questions(spec)
    b = clarifying_questions(spec)
    assert a == b  # deterministic

    keys = [(-q.priority, q.measurand) for q in a]
    assert keys == sorted(keys)  # documented ordering
    present_set = set(present)
    for q in a:
        assert q.measurand not in present_set  # never ask for something already declared
        assert q.priority >= 1
