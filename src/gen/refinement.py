"""Verify -> refine loop — closing the gate-failure feedback cycle (research #2).

A gate is a checker: it returns PASS, or FAIL with reasons. The SOTA finding (Self-
Refine; ReVeal; "LLMs are better at verifying than generating") is that the value comes
from turning each failure into TARGETED feedback that drives a re-generation, bounded so
it cannot oscillate forever. This module is that controller — the deterministic loop
around any gate, with the actual re-generation step left PLUGGABLE.

It carries GENESIS's honesty discipline into the loop:

  • Each gate failure becomes a `RefinementDirective` — a stable instruction for what a
    regenerator must change (which claim/quantity/check, and to what end). The mapping is
    a declared table, not a guess.
  • The loop is BOUNDED (`max_rounds`, default 5 — the literature's anti-oscillation cap)
    and detects NO-PROGRESS: if a regeneration round leaves the exact same failure
    signature, the loop stops and reports `stuck=True`. It NEVER reports convergence it
    did not achieve — an exhausted or stuck loop returns `converged=False` with the
    residual failures, the loop-level analogue of honest abstention.

The `regenerate(state, directives) -> state` callable is where a real run plugs in the
generator (the conductor/agents re-researching or re-deriving). This module is the
deterministic, offline-testable harness around it: a scripted regenerator proves the loop
converges on a fixable defect and honestly gives up on an unfixable one — with no live
model. Offline, pure control flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .core.interfaces import GateFailure, GateResult
from .core.state import RunState

# Declared mapping from a gate-failure code to what a regenerator must do about it. A
# code without an entry gets a generic directive carrying the gate's own detail — the
# loop never fabricates a specific fix it cannot name.
DIRECTIVE_TEMPLATES: dict[str, str] = {
    # delta-physics gate
    "PHYSICS_CHECK_FAILED": "strengthen the design or relax the driving requirement so the check's margin clears",
    "PHYSICS_CHECK_ERROR": "fix the contradictory / uncomputable input the validator rejected",
    "PHYSICS_UNKNOWN_VALIDATOR": "remove the check or add the missing validator model",
    # gamma anti-hallucination gate
    "UNSOURCED_CLAIM": "find a source for the claim or drop it — no sourceless fact",
    "UNSOURCED_STATEMENT": "map the statement to a sourced claim or remove it",
    "REFUTED_AS_FACT": "remove the refuted claim; it cannot be asserted as fact",
    "VALUE_NOT_IN_GROUNDING": "ground the value in a claim whose text contains it, or make it a DECISION",
    "BROKEN_DERIVATION": "recompute the value from its declared inputs",
    "CROSS_CLAIM_CONFLICT": "resolve the contradiction — same-measurand values must agree",
    "DIMENSION_MISMATCH": "fix the unit or formula so the dimensions are homogeneous",
}


@dataclass(frozen=True)
class RefinementDirective:
    """One actionable instruction derived from a gate failure.

    `code`         the gate-failure code that triggered it.
    `target`       the claim_id / quantity / check the failure concerns ("" if global).
    `instruction`  what a regenerator must do to address it.
    `detail`       the gate's own failure detail, carried for context.
    """

    code: str
    target: str
    instruction: str
    detail: str


def directives_from_gate(result: GateResult) -> list[RefinementDirective]:
    """Turn a failed GateResult into targeted refinement directives (one per failure).
    Deterministic; an unknown code yields a generic directive carrying the detail, never
    a fabricated specific fix."""
    out: list[RefinementDirective] = []
    for f in result.failures:
        instruction = DIRECTIVE_TEMPLATES.get(f.code, f"address the gate failure: {f.detail}")
        out.append(RefinementDirective(
            code=f.code, target=f.claim_id or "", instruction=instruction, detail=f.detail,
        ))
    return out


@dataclass
class RefinementResult:
    """Outcome of the verify -> refine loop.

    `converged`         the gate passed within the round budget.
    `rounds`            how many regeneration rounds ran.
    `residual_failures` the failures left if it did NOT converge (empty if it did).
    `stuck`             True if the loop stopped early because a round made no progress
                        (the same failure signature recurred) rather than exhausting
                        the budget — an honest "this regenerator cannot fix it".
    `history`           per-round (round, passed, failure-codes) for audit.
    """

    converged: bool
    rounds: int
    residual_failures: list[GateFailure] = field(default_factory=list)
    stuck: bool = False
    history: list[tuple[int, bool, tuple[str, ...]]] = field(default_factory=list)


def _signature(result: GateResult) -> tuple[tuple[str, str, str], ...]:
    """A stable, collision-free fingerprint of the failure SET: (code, claim_id, detail) per
    failure, sorted. claim_id and detail are kept SEPARATE (no field-value collision) and BOTH
    carried, so "same failure" means same code AND same target AND same reason — an unchanged
    failure is identical, a changed reason is distinct."""
    return tuple(sorted((f.code, f.claim_id or "", f.detail) for f in result.failures))


def refine_until_pass(
    state: RunState,
    regenerate: Callable[[RunState, list[RefinementDirective]], RunState],
    evaluate_gate: Callable[[RunState], GateResult],
    *,
    max_rounds: int = 5,
) -> RefinementResult:
    """Run the verify -> refine loop on `state` under `evaluate_gate`, calling
    `regenerate(state, directives)` to fix each round's failures, until the gate passes
    or the budget is spent.

    Returns a `RefinementResult` that is honest about the outcome: `converged=True` only
    if the gate actually passed; `stuck=True` if a regeneration round left the identical
    failures (no progress); otherwise `converged=False` with the residual failures after
    `max_rounds`. Deterministic given a deterministic `regenerate`. Raises ValueError on a
    non-positive round budget.
    """
    if max_rounds < 1:
        raise ValueError("max_rounds must be >= 1")
    history: list[tuple[int, bool, tuple[str, ...]]] = []
    seen: set[tuple[tuple[str, str, str], ...]] = set()
    for rnd in range(max_rounds + 1):
        result = evaluate_gate(state)
        history.append((rnd, result.passed, tuple(f.code for f in result.failures)))
        if result.passed:
            return RefinementResult(True, rnd, [], False, history)
        signature = _signature(result)
        if signature in seen:                  # this failure set RECURRED -> no progress, stop.
            #                                    Catches A<->B oscillation, not only a consecutive
            #                                    repeat (matches the "recurred" honesty contract).
            return RefinementResult(False, rnd, list(result.failures), True, history)
        seen.add(signature)
        if rnd == max_rounds:                  # budget spent without convergence
            return RefinementResult(False, rnd, list(result.failures), False, history)
        state = regenerate(state, directives_from_gate(result))
    raise AssertionError("unreachable")        # pragma: no cover
