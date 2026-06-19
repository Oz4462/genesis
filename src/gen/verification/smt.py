"""SMT (Z3) gate — upgrade a point-evaluation closed-form screen to a MACHINE-CHECKED guarantee.

GENESIS's δ-physics validators evaluate a safety inequality at ONE nominal operating point. An SMT
prover lifts that to a UNIVERSALLY-quantified guarantee: ``∀ inputs in the modelled envelope, the
bound holds`` — proved, not sampled. The construction (researched, FOVER/BarrierBench pattern): assert
the NEGATION of the bound over the input box and ask Z3; ``unsat`` means no violating point exists
(the bound is proved for the whole box), ``sat`` returns a concrete COUNTEREXAMPLE — the falsifying
input, which is exactly the signal a CEGIS refine loop needs.

This is a proof-of-concept on ONE existing validator: the cantilever bending-stress yield screen
``σ_nom = 6·F·L/(b·h²) ≤ σ_allow`` (``structural.cantilever_bending_stress_formula``). On a degenerate
(point) box the SMT verdict must MATCH the closed-form point check; on a real box it proves the worst
case. Promotion of an ``SmtGate`` into the δ-physics gate set is gated behind that agreement (a
follow-up); this module is the verified primitive.

Honest boundaries (Agent-3 research note, not invented):
  * Z3 here reasons over EXACT reals. It proves the MODEL (the algebra), never correspondence to
    reality — empirical constants (S-N curves, μ), tolerances and model fidelity stay GENESIS's
    closed-form/empirical concern. A proved bound means "the math is safe over the box", not "the part
    survives".
  * ``z3-solver`` is an OPTIONAL dependency. Absent → ``available=False`` (honest abstention, like the
    cadquery/build123d-gated paths), never a fabricated pass/fail.
Deterministic, offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

try:  # z3-solver is optional; its absence is an honest abstention, not a failure
    import z3

    HAVE_Z3 = True
except ImportError:  # pragma: no cover - exercised on machines without z3
    HAVE_Z3 = False

Box = tuple[float, float]


def _as_box(x: float | tuple[float, float]) -> Box:
    """A scalar becomes a degenerate point box ``(x, x)``; a pair passes through as ``(lo, hi)``."""
    if isinstance(x, (int, float)):
        return (float(x), float(x))
    lo, hi = x
    return (float(lo), float(hi))


def _to_float(val) -> float:
    """A Z3 model number (rational OR algebraic) as a Python float."""
    try:
        return float(val.as_fraction())          # RatNumRef / IntNumRef
    except Exception:  # noqa: BLE001 - algebraic numbers have no exact fraction
        return float(val.as_decimal(30).rstrip("?"))


@dataclass(frozen=True)
class SmtProof:
    """Outcome of an SMT bound proof.

    ``available`` is False when z3 is not installed (cannot prove — honest abstention). ``proved`` is
    True only when the bound holds for EVERY point in the box. ``counterexample`` is a concrete
    falsifying input when ``proved`` is False and one was found (the CEGIS signal).
    """

    available: bool
    proved: bool
    counterexample: dict[str, float] = field(default_factory=dict)
    detail: str = ""


def prove_nonpositive(
    build: Callable[[dict[str, "z3.ArithRef"]], "z3.ArithRef"],
    bounds: dict[str, Box],
) -> SmtProof:
    """Prove ``build(vars) ≤ 0`` for ALL ``vars`` inside their ``[lo, hi]`` boxes.

    ``build`` maps a dict of Z3 reals (one per name in ``bounds``) to a Z3 arithmetic expression. The
    method asserts the box constraints AND the negation ``build(vars) > 0``: ``unsat`` ⇒ proved for the
    whole box; ``sat`` ⇒ the model is a counterexample; ``unknown`` ⇒ not proved (reported honestly).
    """
    if not HAVE_Z3:
        return SmtProof(False, False, detail="z3-solver not installed")
    rvars = {name: z3.Real(name) for name in bounds}
    solver = z3.Solver()
    for name, (lo, hi) in bounds.items():
        solver.add(rvars[name] >= lo, rvars[name] <= hi)
    solver.add(build(rvars) > 0)                 # negation of "≤ 0 everywhere"
    result = solver.check()
    if result == z3.unsat:
        return SmtProof(True, True, detail="bound holds for every point in the box")
    if result == z3.sat:
        model = solver.model()
        ce = {name: _to_float(model[rvars[name]]) for name in bounds if model[rvars[name]] is not None}
        return SmtProof(True, False, counterexample=ce, detail="found a falsifying point")
    return SmtProof(True, False, detail=f"z3 returned {result}")


def cantilever_stress(force: float, arm: float, breadth: float, depth: float) -> float:
    """``σ_nom = 6·F·L/(b·h²)`` — the closed-form point value (mirrors structural.py), for cross-check."""
    return 6.0 * force * arm / (breadth * depth * depth)


def prove_cantilever_within_yield(
    *,
    force: float | tuple[float, float],
    arm: float | tuple[float, float],
    breadth: float | tuple[float, float],
    depth: float | tuple[float, float],
    sigma_allow: float,
) -> SmtProof:
    """Machine-check ``6·F·L/(b·h²) ≤ σ_allow`` for ALL (F, L, b, h) in the given boxes.

    Rewritten as the polynomial ``6·F·L − σ_allow·b·h² ≤ 0`` (multiplying through by ``b·h² > 0``) so it
    stays in Z3's nonlinear-real-arithmetic fragment. Each of force/arm/breadth/depth is a scalar
    (point check) or an ``(lo, hi)`` box (worst-case proof). ``breadth``/``depth`` must have a positive
    lower bound, else the rewrite is invalid and the proof is refused.
    """
    bounds = {
        "F": _as_box(force), "L": _as_box(arm), "b": _as_box(breadth), "h": _as_box(depth),
    }
    if bounds["b"][0] <= 0.0 or bounds["h"][0] <= 0.0:
        return SmtProof(HAVE_Z3, False, detail="breadth/depth lower bound must be > 0 for the rewrite")
    return prove_nonpositive(
        lambda v: 6.0 * v["F"] * v["L"] - sigma_allow * v["b"] * v["h"] * v["h"],
        bounds,
    )
