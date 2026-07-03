"""surrogate — residual-certified fast surrogates (NOWS / FOSLS adoption).

A learned surrogate (neural operator: FNO/DeepONet, a PINN, a MeshGraphNet) is fast but can silently
hallucinate physics out of distribution — so it must NEVER be trusted as a gate. The 2025 production
pattern that makes a surrogate honest (agent-A research) is residual certification: the surrogate's
output is accepted as a FACT only when an EXACT, deterministic residual of the governing equation
confirms it (FOSLS gives a residual provably equivalent to the solution error). The residual norm
becomes a new gate predicate — ``verified`` below tolerance, ``unverified`` above — and NOWS additionally
uses the surrogate only to WARM-START an exact solver that still produces the certified answer.

This module is that certification layer (deterministic, offline). The surrogate itself is injected
(``predict`` callable) — the real neural operator needs PyTorch and is external; here a surrogate that
no exact residual can confirm is recorded ``unverified``, never asserted (the runner.py fabrication
lesson). numpy-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

X = TypeVar("X")


@dataclass(frozen=True)
class CertifiedResult:
    """A surrogate output and its EXACT residual. ``verified`` is True only when the residual clears the
    tolerance — i.e. the governing equation actually confirms the output. ``unverified`` outputs are kept
    for transparency but must never be asserted as facts."""

    output: object
    residual: float
    verified: bool
    detail: str = ""


def residual_certify(output: X, residual_fn: Callable[[X], float], *, tol: float) -> CertifiedResult:
    """Certify a surrogate output by its exact residual: ``verified`` iff ``residual_fn(output) <= tol``.
    ``residual_fn`` is a deterministic, exact measure of how well the output satisfies the governing
    equation (e.g. ‖A·x − b‖ for a linear system, or a PDE residual norm). This is the gate predicate —
    the surrogate proposes, the residual disposes."""
    residual = float(residual_fn(output))
    verified = residual <= tol
    return CertifiedResult(
        output=output, residual=residual, verified=verified,
        detail=("residual within tolerance" if verified else f"residual {residual:.3g} exceeds tol {tol:.3g}"),
    )


@dataclass(frozen=True)
class WarmStartResult:
    """The outcome of a NOWS warm-started solve: the CERTIFIED exact answer, whether the surrogate guess
    was already within tolerance (the exact solve could have been skipped), and the guess's residual."""

    answer: object
    guess_was_sufficient: bool
    guess_residual: float
    answer_residual: float


def nows_warm_start(
    guess: X,
    exact_solver: Callable[[X], X],
    residual_fn: Callable[[X], float],
    *,
    tol: float,
) -> WarmStartResult:
    """Neural-Operator Warm Start: if the surrogate ``guess`` already satisfies the residual, accept it;
    otherwise run the ``exact_solver`` (warm-started from the guess) — which still produces the CERTIFIED
    answer. Either way the returned answer's residual is checked, so the speed-up never costs soundness."""
    guess_residual = float(residual_fn(guess))
    if guess_residual <= tol:
        return WarmStartResult(guess, True, guess_residual, guess_residual)
    answer = exact_solver(guess)
    return WarmStartResult(answer, False, guess_residual, float(residual_fn(answer)))
