"""CEGIS — counterexample-guided refine loop: a gate FAILURE returns the falsifying point, not "fail".

Adapted from the control-synthesis pattern (H∞/BarrierBench, the strongest *sound, LLM-independent*
mechanism the cross-domain research surfaced): when a deterministic check fails, it returns the
specific violating quantity + by how much (a ``Counterexample``); a ``repair`` uses that to propose a
corrected candidate; the loop iterates until the gate passes or a bound is hit. This upgrades a gate
from one-shot pass/fail into a generate→falsify→refine loop.

Two invariants keep it honest (CLAUDE.md §1/§2):
  * The CHECK is the sole authority. ``repair`` only PROPOSES a new candidate; nothing is accepted
    until ``check`` returns ``None`` (pass). A repair can never declare success on its own.
  * The loop is BOUNDED. It returns ``converged=False`` with the unresolved counterexample after
    ``max_iterations`` rather than looping forever — a blocked repair is reported, never hidden.

It composes with the SMT gate (``verification/smt.py``): that gate's ``counterexample`` (the worst-case
operating point) is exactly the falsifying point this loop refines against. Deterministic iff ``check``
and ``repair`` are; offline; no new dependencies. The worked example here is the cantilever yield
screen ``σ = 6·F·L/(b·h²) ≤ σ_allow`` (mirrors ``structural.cantilever_bending_stress_formula``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

C = TypeVar("C")  # the candidate (a design / spec / value) being refined


@dataclass(frozen=True)
class Counterexample:
    """A structured gate failure: which quantity violated its bound, its value, and the bound — so a
    refine loop can act on WHY it failed instead of a bare boolean."""

    quantity: str
    value: float
    bound: float
    detail: str = ""

    @property
    def margin(self) -> float:
        """Signed violation ``value − bound`` (> 0 means the bound is exceeded; the amount to close)."""
        return self.value - self.bound


@dataclass(frozen=True)
class CegisResult(Generic[C]):
    """Outcome of a refine loop: whether the check finally passed, how many iterations it took, the
    final candidate, the full ``(candidate, counterexample)`` trajectory (transparency), and the
    UNRESOLVED counterexample when it did not converge."""

    converged: bool
    iterations: int
    candidate: C
    history: tuple[tuple[C, Counterexample], ...] = ()
    counterexample: Counterexample | None = None


def refine(
    initial: C,
    check: Callable[[C], Counterexample | None],
    repair: Callable[[C, Counterexample], C],
    *,
    max_iterations: int = 8,
) -> CegisResult[C]:
    """Run the CEGIS loop. ``check`` returns ``None`` on pass or a ``Counterexample`` on fail; ``repair``
    maps ``(candidate, counterexample)`` to a corrected candidate. Iterates until a candidate passes or
    ``max_iterations`` is reached (then returns ``converged=False`` with the unresolved counterexample).
    The check is the authority — a candidate is only ever returned as converged after it PASSES."""
    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    candidate = initial
    history: list[tuple[C, Counterexample]] = []
    for i in range(max_iterations):
        ce = check(candidate)
        if ce is None:
            return CegisResult(True, i, candidate, tuple(history), None)
        history.append((candidate, ce))
        candidate = repair(candidate, ce)
    ce = check(candidate)  # one final check after the last repair
    if ce is None:
        return CegisResult(True, max_iterations, candidate, tuple(history), None)
    return CegisResult(False, max_iterations, candidate, tuple(history), ce)


# --- worked example: cantilever yield, the check/repair pair the tests drive --------------------

def cantilever_yield_check(design: dict[str, float], sigma_allow: float) -> Counterexample | None:
    """Closed-form yield check of a cantilever design ``{F, L, b, h}``: ``σ = 6·F·L/(b·h²) ≤ σ_allow``.
    Returns a ``Counterexample`` (quantity ``bending_stress``) when the stress exceeds the allowable."""
    sigma = 6.0 * design["F"] * design["L"] / (design["b"] * design["h"] * design["h"])
    if sigma <= sigma_allow:
        return None
    return Counterexample(
        "bending_stress", sigma, sigma_allow,
        detail=f"sigma={sigma:.4g} exceeds allowable={sigma_allow:.4g}",
    )


def increase_depth_repair(
    design: dict[str, float], ce: Counterexample, *, step: float = 0.0
) -> dict[str, float]:
    """Repair a yield violation by deepening the section (``σ ∝ 1/h²``). ``step == 0`` sets ``h`` to the
    EXACT requirement ``h = sqrt(6·F·L/(b·σ_allow))`` (plus a tiny margin to clear the bound) — a
    one-shot fix; ``step > 0`` instead multiplies ``h`` by ``(1 + step)`` for a conservative, multi-
    iteration approach. Pure geometry; the gate re-checks the result (repair never declares success)."""
    new = dict(design)
    if step > 0.0:
        new["h"] = design["h"] * (1.0 + step)
    else:
        required = math.sqrt(6.0 * design["F"] * design["L"] / (design["b"] * ce.bound))
        new["h"] = required * (1.0 + 1e-9)  # nudge past the bound so the ≤ check strictly passes
    return new
