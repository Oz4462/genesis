"""Characterization + facade-detector for ``src/gen/inverse_design.py`` (GATE γ⁺).

These tests would FAIL if the inverse-design core were a hollow facade that
returns a canned favorite instead of genuinely recomputing objective values from
spec quantities. They pin the documented contract:

  1. ``objective_value`` recomputes from the candidate's Quantity and rescales by
     unit (1500 mm vs an objective in 'm' -> 1.5), and is proportional in value.
  2. ``dominates`` is a genuine strict Pareto relation on a mixed
     MAXIMIZE/MINIMIZE goal that FLIPS to False the moment one score is worsened.
  3. the documented guards: ``objective_value`` raises ``ObjectiveEvaluationError``
     on a dimensionally-incomparable unit and on an absent quantity_id.
  4. ``gate_gamma_plus`` over a directly-built ParetoFront treats an empty front
     WITH a gap as honest abstention (passes) and an empty front with NO gap as a
     hard NO_PARETO_CANDIDATES failure.

Per the team decision: assert (a) output changes meaningfully with a driving
input and (b) the fail-loud paths fire exactly. Verdict recorded in
docs/audit/DEPTH_AUDIT_inverse_design.md.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.core.state import (
    DesignObjective,
    InverseDesignGoal,
    ObjectiveDirection,
    ParetoFront,
    Quantity,
    Question,
    RunState,
    Specification,
    ValueOrigin,
)
from gen.inverse_design import (
    ObjectiveEvaluationError,
    dominates,
    gate_gamma_plus,
    objective_value,
)


def _quantity(qid: str, value: float, unit: str) -> Quantity:
    """A minimal DECISION-origin quantity (no grounding/derivation needed for the
    pure objective-value arithmetic under test)."""
    return Quantity(
        id=qid,
        name=qid.replace("_", " "),
        value=value,
        unit=unit,
        origin=ValueOrigin.DECISION,
        rationale="characterization fixture",
    )


def _spec(*quantities: Quantity) -> Specification:
    return Specification(run_id="char-run", idea="characterization", quantities=list(quantities))


# --- (1) objective_value: recomputed and unit-rescaled, not canned ----------

def test_objective_value_rescales_mm_to_m():
    """1500 mm read against an objective declared in 'm' must equal 1.5 — the
    value is genuinely converted by the mm->m scale (1e-3), not echoed."""
    spec = _spec(_quantity("length", 1500.0, "mm"))
    objective = DesignObjective(
        id="obj_len", quantity_id="length", direction=ObjectiveDirection.MINIMIZE, unit="m"
    )
    assert objective_value(spec, objective) == pytest.approx(1.5)


def test_objective_value_is_proportional_to_quantity_value():
    """Changing the driving quantity changes the result proportionally — proof the
    input is consumed, killing any constant-stub facade."""
    objective = DesignObjective(
        id="obj_len", quantity_id="length", direction=ObjectiveDirection.MINIMIZE, unit="m"
    )
    one = objective_value(_spec(_quantity("length", 1500.0, "mm")), objective)
    two = objective_value(_spec(_quantity("length", 3000.0, "mm")), objective)
    assert two == pytest.approx(2.0 * one)
    assert two == pytest.approx(3.0)


@settings(max_examples=50)
@given(
    raw_mm=st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    factor=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_objective_value_proportionality_property(raw_mm: float, factor: float):
    """Invariant: objective_value scales linearly in the quantity value (and the
    mm->m conversion is exactly value/1000), for all inputs — not a few points."""
    objective = DesignObjective(
        id="o", quantity_id="x", direction=ObjectiveDirection.MINIMIZE, unit="m"
    )
    base = objective_value(_spec(_quantity("x", raw_mm, "mm")), objective)
    scaled = objective_value(_spec(_quantity("x", raw_mm * factor, "mm")), objective)
    assert base == pytest.approx(raw_mm / 1000.0)
    assert scaled == pytest.approx(base * factor)


# --- (2) dominates: a genuine strict relation that flips ---------------------

def _mixed_goal() -> InverseDesignGoal:
    """Goal with one MAXIMIZE (efficiency) and one MINIMIZE (mass) objective."""
    return InverseDesignGoal(
        id="mixed",
        description="maximize efficiency, minimize mass",
        objectives=[
            DesignObjective(
                id="eff", quantity_id="eff", direction=ObjectiveDirection.MAXIMIZE, unit="1"
            ),
            DesignObjective(
                id="mass", quantity_id="mass", direction=ObjectiveDirection.MINIMIZE, unit="kg"
            ),
        ],
    )


def test_dominates_strict_on_mixed_goal():
    """A (higher efficiency, lower mass) genuinely dominates B on the mixed goal."""
    goal = _mixed_goal()
    a = {"eff": 0.9, "mass": 2.0}  # better efficiency, lower mass
    b = {"eff": 0.5, "mass": 5.0}
    assert dominates(a, b, goal) is True
    # Domination is asymmetric — B does not dominate A.
    assert dominates(b, a, goal) is False


def test_dominates_flips_when_one_objective_made_worse():
    """Worsen A's mass past B's so A is no longer no-worse on every axis — the
    relation must FLIP to False. A constant 'A wins' facade would not flip."""
    goal = _mixed_goal()
    b = {"eff": 0.5, "mass": 5.0}
    dominating = {"eff": 0.9, "mass": 2.0}
    assert dominates(dominating, b, goal) is True
    worsened = {"eff": 0.9, "mass": 6.0}  # mass now heavier than B
    assert dominates(worsened, b, goal) is False


def test_dominates_false_when_equal():
    """Equal scores are not strict domination (no objective is strictly better)."""
    goal = _mixed_goal()
    same = {"eff": 0.7, "mass": 3.0}
    assert dominates(same, dict(same), goal) is False


# --- (3) documented fail-loud guards ----------------------------------------

def test_objective_value_raises_on_incomparable_unit():
    """A 'kg' quantity cannot be read into a 'm' objective — dimensional mismatch
    must fail loud, never silently return a number."""
    spec = _spec(_quantity("thing", 5.0, "kg"))
    objective = DesignObjective(
        id="o", quantity_id="thing", direction=ObjectiveDirection.MINIMIZE, unit="m"
    )
    with pytest.raises(ObjectiveEvaluationError):
        objective_value(spec, objective)


def test_objective_value_raises_on_absent_quantity():
    """An objective pointing at a quantity_id the spec does not contain must fail
    loud rather than fabricate a value."""
    spec = _spec(_quantity("present", 1.0, "m"))
    objective = DesignObjective(
        id="o", quantity_id="missing", direction=ObjectiveDirection.MINIMIZE, unit="m"
    )
    with pytest.raises(ObjectiveEvaluationError):
        objective_value(spec, objective)


# --- (4) gate_gamma_plus abstention vs hard failure --------------------------

def _state() -> RunState:
    return RunState(question=Question(raw="inverse design", run_id="char-run"))


def _front(gaps: list[str]) -> ParetoFront:
    return ParetoFront(goal=_mixed_goal(), candidates=[], evaluated_candidates=[], gaps=gaps)


def test_gate_gamma_plus_empty_front_with_gap_is_honest_abstention():
    """Empty front + an explicit gap is honest 'ich weiß es nicht' — it passes."""
    result = gate_gamma_plus(_state(), _front(["No candidate specs were supplied."]))
    assert result.passed is True
    assert result.failures == []


def test_gate_gamma_plus_empty_front_without_gap_fails_loud():
    """Empty front + NO gap is a silent void — must fail with NO_PARETO_CANDIDATES."""
    result = gate_gamma_plus(_state(), _front([]))
    assert result.passed is False
    assert any(f.code == "NO_PARETO_CANDIDATES" for f in result.failures)
