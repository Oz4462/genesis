"""Phase gamma+ acceptance — inverse design as a validated Pareto front.

The gate is deterministic and LLM-free: candidate specs must pass GATE gamma, the delta
physics assessment must be `physics_verified`, objective values are recomputed from the
spec quantities, and the asserted front must be nondominated and complete over the
evaluated candidate pool.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    DesignCandidate,
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
from gen.inverse_design import (  # noqa: E402
    build_pareto_front,
    gate_gamma_plus,
    objective_values,
)


def _q(qid: str, value: float, unit: str, measurand: str | None = None) -> Quantity:
    return Quantity(
        id=qid,
        name=qid,
        value=value,
        unit=unit,
        origin=ValueOrigin.DECISION,
        rationale="inverse-design candidate input",
        measurand=measurand,
    )


def _shaft_spec(run_id: str, *, diameter: float, cost: float) -> Specification:
    return Specification(
        run_id=run_id,
        idea="torsion shaft candidate",
        quantities=[
            _q("q_torque", 5.0, "N*m", "shaft.torque"),
            _q("q_d", diameter, "mm", "shaft.diameter"),
            _q("q_len", 1000.0, "mm", "shaft.length"),
            _q("q_g", 80000.0, "MPa", "material.shear_modulus"),
            _q("q_strength", 100.0, "MPa", "material.shear_strength"),
            _q("q_cost", cost, "1"),
        ],
    )


def _candidate(cid: str, diameter: float, cost: float) -> DesignCandidate:
    return DesignCandidate(
        id=cid,
        specification=_shaft_spec(cid, diameter=diameter, cost=cost),
    )


def _goal() -> InverseDesignGoal:
    return InverseDesignGoal(
        id="g1",
        description="minimize shaft diameter and normalized cost while passing torsion",
        objectives=[
            DesignObjective(
                id="min_diameter",
                quantity_id="q_d",
                direction=ObjectiveDirection.MINIMIZE,
                unit="mm",
            ),
            DesignObjective(
                id="min_cost",
                quantity_id="q_cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="1",
            ),
        ],
    )


def _state() -> RunState:
    return RunState(question=Question(raw="inverse shaft", run_id="r-gamma-plus"))


def _values(candidate: DesignCandidate, goal: InverseDesignGoal) -> DesignCandidate:
    return DesignCandidate(
        id=candidate.id,
        specification=candidate.specification,
        objective_values=objective_values(candidate.specification, goal),
    )


def test_structural_goal_guards():
    with pytest.raises(ValueError):
        InverseDesignGoal(id="g0", description="x", objectives=[])
    with pytest.raises(ValueError):
        InverseDesignGoal(
            id="g0",
            description="x",
            objectives=[
                DesignObjective("o", "q", ObjectiveDirection.MINIMIZE, "1"),
                DesignObjective("o", "q2", ObjectiveDirection.MINIMIZE, "1"),
            ],
        )
    with pytest.raises(ValueError):
        DesignObjective("target", "q", ObjectiveDirection.TARGET, "mm")


def test_builder_returns_validated_pareto_front():
    goal = _goal()
    candidates = [
        _candidate("thin_expensive", 20.0, 10.0),
        _candidate("thick_cheap", 30.0, 6.0),
        _candidate("dominated", 30.0, 12.0),
        _candidate("too_thin", 5.0, 1.0),
    ]

    front = build_pareto_front(_state(), goal, candidates)
    assert {candidate.id for candidate in front.candidates} == {"thin_expensive", "thick_cheap"}
    assert {candidate.id for candidate in front.evaluated_candidates} == {
        "thin_expensive",
        "thick_cheap",
        "dominated",
    }
    assert any("too_thin" in gap and "physics_failed" in gap for gap in front.gaps)
    assert gate_gamma_plus(_state(), front).passed


def test_dominated_candidate_on_front_fails():
    goal = _goal()
    evaluated = [
        _values(_candidate("thin_expensive", 20.0, 10.0), goal),
        _values(_candidate("thick_cheap", 30.0, 6.0), goal),
        _values(_candidate("dominated", 30.0, 12.0), goal),
    ]
    front = ParetoFront(
        goal=goal,
        candidates=[evaluated[2]],
        evaluated_candidates=evaluated,
    )

    res = gate_gamma_plus(_state(), front)
    assert not res.passed
    assert any(f.code == "DOMINATED_CANDIDATE" for f in res.failures)


def test_omitted_nondominated_candidate_fails_completeness():
    goal = _goal()
    evaluated = [
        _values(_candidate("thin_expensive", 20.0, 10.0), goal),
        _values(_candidate("thick_cheap", 30.0, 6.0), goal),
        _values(_candidate("dominated", 30.0, 12.0), goal),
    ]
    front = ParetoFront(
        goal=goal,
        candidates=[evaluated[0]],
        evaluated_candidates=evaluated,
    )

    res = gate_gamma_plus(_state(), front)
    assert not res.passed
    assert any(f.code == "PARETO_FRONT_INCOMPLETE" for f in res.failures)


def test_fake_objective_value_fails_recompute():
    goal = _goal()
    candidate = _values(_candidate("thin_expensive", 20.0, 10.0), goal)
    candidate.objective_values["min_diameter"] = 999.0
    front = ParetoFront(goal=goal, candidates=[candidate], evaluated_candidates=[candidate])

    res = gate_gamma_plus(_state(), front)
    assert not res.passed
    assert any(f.code == "OBJECTIVE_VALUE_MISMATCH" for f in res.failures)


def test_candidate_must_be_delta_validated():
    goal = _goal()
    candidate = _values(_candidate("too_thin", 5.0, 1.0), goal)
    front = ParetoFront(goal=goal, candidates=[candidate], evaluated_candidates=[candidate])

    res = gate_gamma_plus(_state(), front)
    assert not res.passed
    assert any(f.code == "CANDIDATE_NOT_VALIDATED" for f in res.failures)


def test_empty_front_with_gap_is_honest_abstention():
    front = build_pareto_front(_state(), _goal(), [])
    assert front.candidates == []
    assert front.gaps
    assert gate_gamma_plus(_state(), front).passed
