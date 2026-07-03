"""Phase delta+ coverage proof: declared failure modes and honest residual gaps.

The reality proof answers "did this measured prediction survive contact with the world?".
The coverage proof answers the orthogonal question from HORIZON.md: "which failure modes
did we check, and which indicated modes remain uncheckable?"

This module is gate-first and deterministic. It derives the failure modes Genesis can
currently know without model judgment:

* physics modes indicated by ``physics_selection.RECIPES`` triggers;
* global constraint feasibility over the spec's constraints, via optional SMT.

A later N-judge critic can add more ``FailureMode`` objects to a certificate, but the
completion gate below does not depend on model calls. It only verifies that every
deterministically indicated mode is declared and covered as either CHECKED or UNTESTABLE.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .core.interfaces import GateFailure, GateResult
from .core.state import (
    CoverageCertificate,
    CoverageStatus,
    FailureMode,
    FailureModeCoverage,
    Specification,
)
from .physics_selection import RECIPES, CheckRecipe, select_physics_checks


@dataclass(frozen=True)
class CoverageRequirement:
    """One failure mode the certificate must cover, plus the expected coverage kind."""

    mode: FailureMode
    expected_status: CoverageStatus
    evidence: str


def physics_mode_id(recipe: CheckRecipe) -> str:
    """Stable id for a physics-selector failure mode."""
    return f"physics:{recipe.trigger}:{recipe.validator}"


def _constraint_mode_id() -> str:
    return "smt:constraint_feasibility"


def _spec_measurands(spec: Specification) -> set[str]:
    return {q.measurand for q in spec.quantities if q.measurand}


def _gap_for(recipe: CheckRecipe, gaps: list[str]) -> str:
    prefix = f"{recipe.name} ({recipe.validator})"
    for gap in gaps:
        if gap.startswith(prefix):
            return gap
    return f"{prefix} is indicated by {recipe.trigger!r}, but no runnable check was assembled."


def _smt_requirement(spec: Specification) -> CoverageRequirement | None:
    if not spec.constraints:
        return None

    grounding = [f"constraint:{c.id}" for c in spec.constraints]
    mode = FailureMode(
        id=_constraint_mode_id(),
        label="global constraint feasibility",
        source="constraint_smt",
        grounding=grounding,
    )
    try:
        from .verification.constraint_smt import check_feasibility
    except ImportError:
        return CoverageRequirement(
            mode=mode,
            expected_status=CoverageStatus.UNTESTABLE,
            evidence=(
                "SMT feasibility not run: z3-solver is unavailable, so global "
                "constraint infeasibility remains an explicit residual gap."
            ),
        )

    try:
        result = check_feasibility(spec.constraints)
    except RuntimeError as exc:
        return CoverageRequirement(
            mode=mode,
            expected_status=CoverageStatus.UNTESTABLE,
            evidence=f"SMT feasibility not proven: {exc}",
        )

    if result.feasible:
        evidence = "smt:feasible"
    else:
        evidence = "smt:infeasible:unsat_core=" + ",".join(result.conflicting_ids)
    return CoverageRequirement(mode=mode, expected_status=CoverageStatus.CHECKED, evidence=evidence)


def coverage_requirements(
    spec: Specification,
    *,
    reviewed_failure_modes: Iterable[FailureMode] = (),
) -> list[CoverageRequirement]:
    """Derive the deterministic failure modes a spec currently indicates.

    The list is stable: physics recipes keep catalog order, then the SMT feasibility mode
    is appended when the spec has constraints. No LLMs, no inference beyond declared
    measurand tags and explicit constraints.
    """
    measurands = _spec_measurands(spec)
    checks, gaps = select_physics_checks(spec)
    check_by_key = {(check.name, check.validator): check for check in checks}

    requirements: list[CoverageRequirement] = []
    for recipe in RECIPES:
        if recipe.trigger not in measurands:
            continue
        mode = FailureMode(
            id=physics_mode_id(recipe),
            label=recipe.name,
            source="physics_selection",
            grounding=[f"measurand:{recipe.trigger}"],
        )
        check = check_by_key.get((recipe.name, recipe.validator))
        if check is None:
            requirements.append(
                CoverageRequirement(
                    mode=mode,
                    expected_status=CoverageStatus.UNTESTABLE,
                    evidence=_gap_for(recipe, gaps),
                )
            )
        else:
            requirements.append(
                CoverageRequirement(
                    mode=mode,
                    expected_status=CoverageStatus.CHECKED,
                    evidence=f"physics_check:{check.name}:{check.validator}",
                )
            )

    smt_req = _smt_requirement(spec)
    if smt_req is not None:
        requirements.append(smt_req)
    for mode in reviewed_failure_modes:
        requirements.append(
            CoverageRequirement(
                mode=mode,
                expected_status=CoverageStatus.UNTESTABLE,
                evidence=(
                    f"reviewed failure mode {mode.id!r} has no deterministic validator "
                    "mapped yet; keep it as an explicit residual risk."
                ),
            )
        )
    return requirements


def build_coverage_certificate(
    spec: Specification,
    *,
    reviewed_failure_modes: Iterable[FailureMode] = (),
) -> CoverageCertificate:
    """Build the baseline delta+ coverage certificate for a spec.

    This is intentionally mechanical: it certifies only what the selector and optional SMT
    can prove today. Model-discovered failure modes can be appended later and will be
    checked by the same gate if they carry grounding and coverage evidence.
    """
    requirements = coverage_requirements(spec, reviewed_failure_modes=reviewed_failure_modes)
    coverage: list[FailureModeCoverage] = []
    for req in requirements:
        if req.expected_status is CoverageStatus.CHECKED:
            coverage.append(
                FailureModeCoverage(
                    mode_id=req.mode.id,
                    status=CoverageStatus.CHECKED,
                    evidence=[req.evidence],
                )
            )
        else:
            coverage.append(
                FailureModeCoverage(
                    mode_id=req.mode.id,
                    status=CoverageStatus.UNTESTABLE,
                    evidence=[req.evidence],
                    residual_risk=req.evidence,
                )
            )
    return CoverageCertificate(
        spec_run_id=spec.run_id,
        failure_modes=[req.mode for req in requirements],
        coverage=coverage,
        complete=True,
        produced_by="coverage_builder",
    )


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def gate_delta_plus_coverage(
    spec: Specification,
    certificate: CoverageCertificate,
    *,
    reviewed_failure_modes: Iterable[FailureMode] = (),
) -> GateResult:
    """GATE delta+ coverage — hard completion predicate for the coverage proof.

    It verifies:
      DC-1 CERTIFICATE_SPEC_MISMATCH       certificate belongs to this spec run.
      DC-2 NOT_COMPLETE_CERTIFICATE        no "complete" claim without the flag.
      DC-3 DUPLICATE_FAILURE_MODE          no ambiguous mode declarations.
      DC-4 DUPLICATE_COVERAGE              no ambiguous coverage entries.
      DC-5 UNDECLARED_FAILURE_MODE         every indicated mode is declared.
      DC-6 FAILURE_MODE_GROUNDING_MISMATCH declaration carries the real trigger.
      DC-7 UNCOVERED_FAILURE_MODE          every declared/required mode has coverage.
      DC-8 REQUIRED_CHECK_NOT_PERFORMED    checkable mode was called untestable/missing.
      DC-9 UNRUNNABLE_MODE_CLAIMED_CHECKED unrunnable mode was falsely called checked.
      DC-10 COVERAGE_WITHOUT_EVIDENCE      checked/untestable status lacks proof text.

    Honest failure is allowed: a physics check or SMT proof may find a failing design.
    This gate certifies coverage, not success.
    """
    failures: list[GateFailure] = []

    if certificate.spec_run_id != spec.run_id:
        failures.append(
            GateFailure(
                code="CERTIFICATE_SPEC_MISMATCH",
                detail=(
                    f"certificate belongs to run {certificate.spec_run_id!r}, "
                    f"not spec run {spec.run_id!r}."
                ),
            )
        )
    if not certificate.complete:
        failures.append(
            GateFailure(
                code="NOT_COMPLETE_CERTIFICATE",
                detail="coverage certificate does not claim completion for indicated modes.",
            )
        )

    mode_ids = [mode.id for mode in certificate.failure_modes]
    for mode_id in sorted(_duplicates(mode_ids)):
        failures.append(
            GateFailure(
                code="DUPLICATE_FAILURE_MODE",
                detail=f"failure mode {mode_id!r} is declared more than once.",
                claim_id=mode_id,
            )
        )

    coverage_ids = [item.mode_id for item in certificate.coverage]
    for mode_id in sorted(_duplicates(coverage_ids)):
        failures.append(
            GateFailure(
                code="DUPLICATE_COVERAGE",
                detail=f"failure mode {mode_id!r} has more than one coverage entry.",
                claim_id=mode_id,
            )
        )

    modes = {mode.id: mode for mode in certificate.failure_modes}
    coverage = {item.mode_id: item for item in certificate.coverage}

    for mode in certificate.failure_modes:
        if not mode.grounding:
            failures.append(
                GateFailure(
                    code="UNGROUNDED_FAILURE_MODE",
                    detail=f"failure mode {mode.id!r} has no grounding.",
                    claim_id=mode.id,
                )
            )

    for item in certificate.coverage:
        if item.mode_id not in modes:
            failures.append(
                GateFailure(
                    code="COVERAGE_FOR_UNKNOWN_MODE",
                    detail=f"coverage references undeclared failure mode {item.mode_id!r}.",
                    claim_id=item.mode_id,
                )
            )
        if item.status is CoverageStatus.CHECKED and not item.evidence:
            failures.append(
                GateFailure(
                    code="COVERAGE_WITHOUT_EVIDENCE",
                    detail=f"checked failure mode {item.mode_id!r} has no evidence.",
                    claim_id=item.mode_id,
                )
            )
        if item.status is CoverageStatus.UNTESTABLE and not item.residual_risk.strip():
            failures.append(
                GateFailure(
                    code="COVERAGE_WITHOUT_EVIDENCE",
                    detail=f"untestable failure mode {item.mode_id!r} has no residual risk.",
                    claim_id=item.mode_id,
                )
            )

    for req in coverage_requirements(spec, reviewed_failure_modes=reviewed_failure_modes):
        declared = modes.get(req.mode.id)
        if declared is None:
            failures.append(
                GateFailure(
                    code="UNDECLARED_FAILURE_MODE",
                    detail=(
                        f"spec indicates failure mode {req.mode.id!r} "
                        f"({req.mode.label}) but the certificate does not declare it."
                    ),
                    claim_id=req.mode.id,
                )
            )
            continue

        missing_grounding = set(req.mode.grounding) - set(declared.grounding)
        if missing_grounding:
            failures.append(
                GateFailure(
                    code="FAILURE_MODE_GROUNDING_MISMATCH",
                    detail=(
                        f"failure mode {req.mode.id!r} is missing grounding "
                        f"{sorted(missing_grounding)!r}."
                    ),
                    claim_id=req.mode.id,
                )
            )

        item = coverage.get(req.mode.id)
        if item is None:
            failures.append(
                GateFailure(
                    code="UNCOVERED_FAILURE_MODE",
                    detail=f"failure mode {req.mode.id!r} has no coverage entry.",
                    claim_id=req.mode.id,
                )
            )
            continue

        if req.expected_status is CoverageStatus.CHECKED and item.status is not CoverageStatus.CHECKED:
            failures.append(
                GateFailure(
                    code="REQUIRED_CHECK_NOT_PERFORMED",
                    detail=(
                        f"failure mode {req.mode.id!r} is runnable and must be CHECKED; "
                        f"certificate says {item.status.value}."
                    ),
                    claim_id=req.mode.id,
                )
            )
        if req.expected_status is CoverageStatus.UNTESTABLE and item.status is CoverageStatus.CHECKED:
            failures.append(
                GateFailure(
                    code="UNRUNNABLE_MODE_CLAIMED_CHECKED",
                    detail=(
                        f"failure mode {req.mode.id!r} is indicated but not runnable "
                        f"({req.evidence}); certificate falsely marks it CHECKED."
                    ),
                    claim_id=req.mode.id,
                )
            )

    return GateResult(gate="delta_plus_coverage", passed=not failures, failures=failures)


__all__ = [
    "CoverageRequirement",
    "build_coverage_certificate",
    "coverage_requirements",
    "gate_delta_plus_coverage",
    "physics_mode_id",
]
