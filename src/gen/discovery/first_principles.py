"""first_principles — First-Principles Discovery Mode (build doc 4.5, Phase 4).

The highest-trust path in the engine. Instead of FITTING a law to data, it DERIVES a target
from axioms using only the allowed arithmetic operations, and every single step is checked by
the gate_c6 machinery — the safe, independent recompute (``verification.derivation``). The
result is a PROOF TREE: a chain of steps, each one re-evaluated and confirmed, from the axioms
to the target. A fitted law is "consistent with the data"; a derived law is "follows from these
premises" — a strictly stronger claim, so it earns the highest confidence.

Two entry points:

  * ``verify_proof`` — given axioms and proposed steps (each ``name = formula(prior names)`` with
    a CLAIMED value), re-evaluate every formula over the accumulated values and confirm the
    claim matches (gate_c6, ``within_tolerance``). A tampered step — a value that does not
    follow from its formula — is caught and the proof fails at exactly that step. This is the
    rigorous core: GENESIS does not take a derivation on faith, it recomputes it.
  * ``derive`` — a BOUNDED first-principles search: combine the axioms with the allowed binary
    operations (+ − × ÷), up to a small number of operations, to reach a target value, and
    return the verified proof. Honest boundary: this is bounded arithmetic derivation over the
    grammar, NOT a general theorem prover; it finds short derivations, and what it finds it
    proves.

Offline, deterministic. The verifier reuses ``verification.derivation`` so a first-principles
proof is checked by the same evaluator the γ gates use — no separate, weaker math path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..verification.derivation import evaluate_formula, within_tolerance

#: Default match tolerance for the gate_c6 recompute of each step.
DEFAULT_TOLERANCE = 1e-9


@dataclass(frozen=True)
class Axiom:
    """A first-principles premise: a named quantity with a value (a GROUNDED starting fact)."""

    name: str
    value: float
    note: str = ""


@dataclass(frozen=True)
class ProofStep:
    """One derivation step: ``name = formula`` over prior names, with the claimed `value`.
    `verified` is set by ``verify_proof`` — True iff the gate_c6 recompute matches the claim."""

    name: str
    formula: str
    value: float
    verified: bool = False


@dataclass(frozen=True)
class ProofTree:
    """A first-principles proof: the axioms, the verified steps, the target, and whether the
    whole chain is proven (every step recomputed AND the target reached)."""

    axioms: tuple[Axiom, ...]
    steps: tuple[ProofStep, ...]
    target_name: str
    target_value: float
    proven: bool


def verify_proof(
    axioms: list[Axiom],
    steps: list[ProofStep],
    *,
    target_name: str | None = None,
    target_value: float | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> ProofTree:
    """Verify a proposed derivation step by step. Each step's `formula` is independently
    re-evaluated over the axioms + already-verified prior steps (``evaluate_formula``) and must
    match the step's claimed `value` within `tolerance` (gate_c6). The proof is `proven` iff
    EVERY step verifies and — when `target_name` is given — that target reaches `target_value`.
    A tampered or non-following step is caught (verified=False) and breaks the proof."""
    known: dict[str, float] = {ax.name: ax.value for ax in axioms}
    verified_steps: list[ProofStep] = []
    all_ok = True
    for step in steps:
        try:
            recomputed = evaluate_formula(step.formula, known)
            ok = math.isfinite(recomputed) and within_tolerance(step.value, recomputed, tolerance=tolerance)
        except Exception:
            ok = False
        verified_steps.append(replace(step, verified=ok))
        all_ok = all_ok and ok
        known[step.name] = step.value  # subsequent steps build on the stated value

    tname = target_name if target_name is not None else (steps[-1].name if steps else "")
    tval = known.get(tname, math.nan)
    target_ok = tname in known and (target_value is None or within_tolerance(target_value, tval, tolerance=tolerance))
    return ProofTree(
        axioms=tuple(axioms), steps=tuple(verified_steps), target_name=tname,
        target_value=target_value if target_value is not None else tval,
        proven=all_ok and target_ok)


_OPS = ("+", "-", "*", "/")


def _try_formula(formula: str, known: dict[str, float], target_value: float, tolerance: float) -> float | None:
    try:
        v = evaluate_formula(formula, known)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return v if within_tolerance(target_value, v, tolerance=tolerance) else None


def derive(
    axioms: list[Axiom],
    target_value: float,
    *,
    target_name: str = "result",
    max_ops: int = 2,
    tolerance: float = DEFAULT_TOLERANCE,
) -> ProofTree | None:
    """Bounded first-principles SEARCH: combine the axioms with the allowed binary operations
    (up to `max_ops` operations) to reach `target_value`, and return the VERIFIED proof tree
    (the found formula re-checked by ``verify_proof``). Returns None if no derivation within the
    bound reaches the target. Not a general theorem prover — a bounded arithmetic search; what
    it finds, it proves. Deterministic (fixed enumeration order)."""
    known = {ax.name: ax.value for ax in axioms}
    names = list(known)

    # 1 operation: x op y
    for x in names:
        for y in names:
            for op in _OPS:
                f = f"{x} {op} {y}"
                v = _try_formula(f, known, target_value, tolerance)
                if v is not None:
                    return verify_proof(axioms, [ProofStep(target_name, f, v)],
                                        target_name=target_name, target_value=target_value,
                                        tolerance=tolerance)
    # 2 operations: (x op1 y) op2 z
    if max_ops >= 2:
        for x in names:
            for y in names:
                for op1 in _OPS:
                    for z in names:
                        for op2 in _OPS:
                            f = f"({x} {op1} {y}) {op2} {z}"
                            v = _try_formula(f, known, target_value, tolerance)
                            if v is not None:
                                return verify_proof(axioms, [ProofStep(target_name, f, v)],
                                                    target_name=target_name, target_value=target_value,
                                                    tolerance=tolerance)
    return None
