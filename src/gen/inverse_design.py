"""Phase gamma+ — inverse design as a validated Pareto front.

HORIZON's inverse-design promise is not "the model picked a good design". It is:

    goal -> candidate specifications -> gamma soundness -> delta fitness oracle
    -> a Pareto front whose objective values are recomputed from the specs.

This module is the deterministic core of that promise. It does not generate candidate
specifications; the architect/model layer may do that later. Given candidates, it filters
for candidates that pass GATE gamma and the delta physics assessment, recomputes objective
values from the candidates' quantities, and proves the front is nondominated and complete
over the evaluated pool.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Iterable

from .core.errors import UnitError
from .core.interfaces import GateFailure, GateResult
from .core.state import (
    DesignCandidate,
    DesignObjective,
    InverseDesignGoal,
    ObjectiveDirection,
    ParetoFront,
    Quantity,
    RunState,
    Specification,
)
from .pipeline import assess_specification
from .verification.derivation import DEFAULT_TOLERANCE
from .verification.gates import gate_gamma
from .verification.units import parse_unit, unit_scale


class ObjectiveEvaluationError(ValueError):
    """Raised when an objective cannot be recomputed from a candidate spec."""


def _quantity_by_id(spec: Specification) -> dict[str, Quantity]:
    return {q.id: q for q in spec.quantities}


def objective_value(spec: Specification, objective: DesignObjective) -> float:
    """Return the candidate's raw objective value in the objective's declared unit."""
    quantity = _quantity_by_id(spec).get(objective.quantity_id)
    if quantity is None:
        raise ObjectiveEvaluationError(
            f"quantity {objective.quantity_id!r} is absent from spec {spec.run_id!r}"
        )
    try:
        if parse_unit(quantity.unit) != parse_unit(objective.unit):
            raise ObjectiveEvaluationError(
                f"quantity {quantity.id!r} unit {quantity.unit!r} is not comparable to "
                f"objective unit {objective.unit!r}"
            )
        scale_from = unit_scale(quantity.unit)
        scale_to = unit_scale(objective.unit)
    except UnitError as exc:
        raise ObjectiveEvaluationError(str(exc)) from exc
    if scale_from is None or scale_to is None:
        raise ObjectiveEvaluationError(
            f"objective {objective.id!r} uses an opaque unit conversion "
            f"({quantity.unit!r} -> {objective.unit!r})"
        )
    return quantity.value * scale_from / scale_to


def objective_values(spec: Specification, goal: InverseDesignGoal) -> dict[str, float]:
    """Recompute every raw objective value from a candidate specification."""
    return {objective.id: objective_value(spec, objective) for objective in goal.objectives}


def objective_score(raw_value: float, objective: DesignObjective) -> float:
    """Convert one objective to a minimization score; lower is better."""
    if objective.direction is ObjectiveDirection.MINIMIZE:
        return raw_value
    if objective.direction is ObjectiveDirection.MAXIMIZE:
        return -raw_value
    assert objective.target is not None
    return abs(raw_value - objective.target)


def _scores(values: dict[str, float], goal: InverseDesignGoal) -> dict[str, float]:
    return {
        objective.id: objective_score(values[objective.id], objective)
        for objective in goal.objectives
    }


def dominates(
    a_values: dict[str, float],
    b_values: dict[str, float],
    goal: InverseDesignGoal,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> bool:
    """True iff candidate A Pareto-dominates candidate B for the goal."""
    a_scores = _scores(a_values, goal)
    b_scores = _scores(b_values, goal)
    no_worse = all(
        a_scores[objective.id] <= b_scores[objective.id] + tolerance
        for objective in goal.objectives
    )
    strictly_better = any(
        a_scores[objective.id] < b_scores[objective.id] - tolerance
        for objective in goal.objectives
    )
    return no_worse and strictly_better


def equivalent_objectives(
    a_values: dict[str, float],
    b_values: dict[str, float],
    goal: InverseDesignGoal,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> bool:
    """True iff two candidates have the same objective scores within tolerance."""
    a_scores = _scores(a_values, goal)
    b_scores = _scores(b_values, goal)
    return all(
        math.isclose(
            a_scores[objective.id],
            b_scores[objective.id],
            rel_tol=tolerance,
            abs_tol=tolerance,
        )
        for objective in goal.objectives
    )


def _probe_state(state: RunState, spec: Specification) -> RunState:
    probe = RunState(question=state.question)
    probe.claims = state.claims
    probe.approaches = state.approaches
    probe.specification = spec
    return probe


def _candidate_is_valid(
    state: RunState,
    candidate: DesignCandidate,
    *,
    confidence_threshold: float,
    derivation_tolerance: float,
) -> tuple[bool, str]:
    gamma = gate_gamma(
        _probe_state(state, candidate.specification),
        confidence_threshold=confidence_threshold,
        derivation_tolerance=derivation_tolerance,
    )
    if not gamma.passed:
        detail = "; ".join(f"{f.code}: {f.detail}" for f in gamma.failures[:3])
        return False, f"gamma failed: {detail}"

    assessment = assess_specification(candidate.specification, claims=state.claims)
    if assessment.overall != "physics_verified":
        return False, f"delta fitness is {assessment.overall}"
    return True, ""


def build_pareto_front(
    state: RunState,
    goal: InverseDesignGoal,
    candidates: Iterable[DesignCandidate],
    *,
    confidence_threshold: float = 0.7,
    derivation_tolerance: float = DEFAULT_TOLERANCE,
) -> ParetoFront:
    """Build the validated nondominated front over supplied candidate specs."""
    evaluated: list[DesignCandidate] = []
    gaps: list[str] = []

    supplied = list(candidates)
    if not supplied:
        gaps.append("No candidate specifications were supplied for inverse design.")

    for candidate in supplied:
        ok, reason = _candidate_is_valid(
            state,
            candidate,
            confidence_threshold=confidence_threshold,
            derivation_tolerance=derivation_tolerance,
        )
        if not ok:
            gaps.append(f"candidate {candidate.id!r} rejected: {reason}")
            continue
        try:
            values = objective_values(candidate.specification, goal)
        except ObjectiveEvaluationError as exc:
            gaps.append(f"candidate {candidate.id!r} rejected: {exc}")
            continue
        evaluated.append(replace(candidate, objective_values=values))

    front: list[DesignCandidate] = []
    for candidate in evaluated:
        if any(dominates(other.objective_values, candidate.objective_values, goal)
               for other in evaluated if other.id != candidate.id):
            continue
        front.append(candidate)

    return ParetoFront(
        goal=goal,
        candidates=front,
        evaluated_candidates=evaluated,
        gaps=gaps,
        produced_by="inverse_design",
    )


def _duplicate_ids(candidates: list[DesignCandidate]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for candidate in candidates:
        if candidate.id in seen:
            dupes.add(candidate.id)
        seen.add(candidate.id)
    return dupes


def _objective_failures(
    candidate: DesignCandidate,
    goal: InverseDesignGoal,
    *,
    tolerance: float,
) -> list[GateFailure]:
    failures: list[GateFailure] = []
    try:
        expected = objective_values(candidate.specification, goal)
    except ObjectiveEvaluationError as exc:
        return [
            GateFailure(
                code="OBJECTIVE_NOT_RECOMPUTABLE",
                detail=f"candidate {candidate.id!r}: {exc}",
                claim_id=candidate.id,
            )
        ]

    for objective in goal.objectives:
        actual = candidate.objective_values.get(objective.id)
        if actual is None:
            failures.append(
                GateFailure(
                    code="OBJECTIVE_VALUE_MISSING",
                    detail=(
                        f"candidate {candidate.id!r} has no value for objective "
                        f"{objective.id!r}."
                    ),
                    claim_id=candidate.id,
                )
            )
            continue
        if not math.isfinite(actual) or not math.isclose(
            actual, expected[objective.id], rel_tol=tolerance, abs_tol=tolerance
        ):
            failures.append(
                GateFailure(
                    code="OBJECTIVE_VALUE_MISMATCH",
                    detail=(
                        f"candidate {candidate.id!r} objective {objective.id!r} "
                        f"claims {actual!r}, recomputed {expected[objective.id]!r}."
                    ),
                    claim_id=candidate.id,
                )
            )
    return failures


def gate_gamma_plus(
    state: RunState,
    front: ParetoFront,
    *,
    confidence_threshold: float = 0.7,
    derivation_tolerance: float = DEFAULT_TOLERANCE,
    objective_tolerance: float = DEFAULT_TOLERANCE,
) -> GateResult:
    """GATE gamma+ — validate an inverse-design Pareto front.

    It proves the front is not a single arbitrary favorite:
      GP-1 NO_PARETO_CANDIDATES       no front and no explicit abstention gap.
      GP-2 DUPLICATE_CANDIDATE_ID     ambiguous candidate ids.
      GP-3 FRONT_NOT_EVALUATED        front member is not in the evaluated pool.
      GP-4 CANDIDATE_GAMMA_FAILED     candidate spec fails GATE gamma.
      GP-5 CANDIDATE_NOT_VALIDATED    delta assessment is not physics_verified.
      GP-6 OBJECTIVE_*                objective scores are missing/fake/unrecomputable.
      GP-7 DOMINATED_CANDIDATE        a front member is dominated by another valid candidate.
      GP-8 PARETO_FRONT_INCOMPLETE    a valid evaluated candidate was omitted from front.

    Empty front with gaps is honest abstention and passes. Pure; no model calls.
    """
    failures: list[GateFailure] = []

    if not front.candidates and not front.gaps:
        failures.append(
            GateFailure(
                code="NO_PARETO_CANDIDATES",
                detail="ParetoFront is empty without an explicit abstention gap.",
            )
        )

    pool = front.evaluated_candidates or front.candidates
    for candidate_id in sorted(_duplicate_ids(pool)):
        failures.append(
            GateFailure(
                code="DUPLICATE_CANDIDATE_ID",
                detail=f"candidate id {candidate_id!r} appears more than once.",
                claim_id=candidate_id,
            )
        )
    for candidate_id in sorted(_duplicate_ids(front.candidates)):
        failures.append(
            GateFailure(
                code="DUPLICATE_CANDIDATE_ID",
                detail=f"front candidate id {candidate_id!r} appears more than once.",
                claim_id=candidate_id,
            )
        )

    pool_by_id = {candidate.id: candidate for candidate in pool}
    front_ids = {candidate.id for candidate in front.candidates}
    for candidate in front.candidates:
        if candidate.id not in pool_by_id:
            failures.append(
                GateFailure(
                    code="FRONT_NOT_EVALUATED",
                    detail=f"front candidate {candidate.id!r} is absent from evaluated pool.",
                    claim_id=candidate.id,
                )
            )

    for candidate in pool:
        gamma = gate_gamma(
            _probe_state(state, candidate.specification),
            confidence_threshold=confidence_threshold,
            derivation_tolerance=derivation_tolerance,
        )
        if not gamma.passed:
            detail = "; ".join(f"{f.code}: {f.detail}" for f in gamma.failures[:3])
            failures.append(
                GateFailure(
                    code="CANDIDATE_GAMMA_FAILED",
                    detail=f"candidate {candidate.id!r} fails gamma: {detail}",
                    claim_id=candidate.id,
                )
            )
            continue

        assessment = assess_specification(candidate.specification, claims=state.claims)
        if assessment.overall != "physics_verified":
            failures.append(
                GateFailure(
                    code="CANDIDATE_NOT_VALIDATED",
                    detail=(
                        f"candidate {candidate.id!r} delta fitness is "
                        f"{assessment.overall}, not physics_verified."
                    ),
                    claim_id=candidate.id,
                )
            )
        failures.extend(
            _objective_failures(candidate, front.goal, tolerance=objective_tolerance)
        )

    comparable_pool = [
        candidate for candidate in pool
        if candidate.id in pool_by_id
        and not _objective_failures(candidate, front.goal, tolerance=objective_tolerance)
    ]

    for front_candidate in front.candidates:
        candidate = pool_by_id.get(front_candidate.id, front_candidate)
        for other in comparable_pool:
            if other.id == candidate.id:
                continue
            if dominates(
                other.objective_values,
                candidate.objective_values,
                front.goal,
                tolerance=objective_tolerance,
            ):
                failures.append(
                    GateFailure(
                        code="DOMINATED_CANDIDATE",
                        detail=(
                            f"front candidate {candidate.id!r} is dominated by "
                            f"evaluated candidate {other.id!r}."
                        ),
                        claim_id=candidate.id,
                    )
                )
                break

    for candidate in comparable_pool:
        if candidate.id in front_ids:
            continue
        covered = any(
            dominates(
                pool_by_id[front_id].objective_values,
                candidate.objective_values,
                front.goal,
                tolerance=objective_tolerance,
            )
            or equivalent_objectives(
                pool_by_id[front_id].objective_values,
                candidate.objective_values,
                front.goal,
                tolerance=objective_tolerance,
            )
            for front_id in front_ids
            if front_id in pool_by_id
        )
        if not covered:
            failures.append(
                GateFailure(
                    code="PARETO_FRONT_INCOMPLETE",
                    detail=(
                        f"evaluated candidate {candidate.id!r} is neither on the front "
                        "nor dominated/equivalent to a front candidate."
                    ),
                    claim_id=candidate.id,
                )
            )

    return GateResult(gate="gamma_plus", passed=not failures, failures=failures)


__all__ = [
    "ObjectiveEvaluationError",
    "build_pareto_front",
    "dominates",
    "equivalent_objectives",
    "gate_gamma_plus",
    "objective_score",
    "objective_value",
    "objective_values",
]
