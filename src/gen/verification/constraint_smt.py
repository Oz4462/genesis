"""SMT constraint feasibility via z3 (Tier-3, optional `smt` extra).

`constraint_consistency.find_contradictions` (dependency-free) catches PAIRWISE
contradictions on the same expression pair. Its own docstring names the gap it cannot
close: "TRANSITIVE multi-constraint infeasibility (a>b, b>c, c>a) ... needs a full SMT
solver (e.g. z3)". This module closes exactly that gap, and returns a sufficient conflicting subset (the z3 unsat core; z3 does not minimize it by
default, so it is NOT guaranteed minimal and may vary across z3 builds) so the operator sees
WHICH requirements clash.

Honest boundary: each distinct side-expression string is treated as one real variable
(numeric literals are parsed as constants); compound arithmetic like "a+b" is treated
as an opaque variable, so this proves infeasibility over the *relational* structure, not
full algebra. z3 is heavy, so the import is guarded — GENESIS core stays dependency-light.
"""

from __future__ import annotations

import math
import operator
from dataclasses import dataclass

from ..core.state import Constraint

try:
    import z3
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "z3-solver is required for gen.verification.constraint_smt. "
        "Install the optional extra: pip install -e '.[smt]'."
    ) from exc

_OPS = {
    "lt": operator.lt,
    "le": operator.le,
    "eq": operator.eq,
    "ge": operator.ge,
    "gt": operator.gt,
}


@dataclass(frozen=True)
class FeasibilityResult:
    """Outcome of the global feasibility check over a constraint set.

    `feasible`        True iff some assignment satisfies ALL comparison constraints.
    `conflicting_ids` a sufficient subset of constraint ids that clash (the z3 unsat core;
                      not guaranteed minimal — z3 does not minimize by default) when
                      infeasible; empty when feasible.
    """

    feasible: bool
    conflicting_ids: tuple[str, ...]


def check_feasibility(constraints: list[Constraint]) -> FeasibilityResult:
    """Globally check whether all comparison constraints can hold simultaneously.

    Catches transitive/global infeasibility that the pairwise structural check misses.
    Returns the unsat core (conflicting constraint ids) when infeasible. Constraints
    whose kind is not a comparison are ignored (GATE γ validates kinds separately).
    """
    solver = z3.Solver()
    variables: dict[str, z3.ArithRef] = {}

    def term(expr: str):
        expr = expr.strip()
        try:
            value = float(expr)
        except ValueError:
            value = None
        # Only a FINITE literal is a z3 constant. float() also accepts 'inf'/'nan', which
        # z3.RealVal rejects with an opaque error — treat those (and any non-numeric side) as
        # an opaque variable so the constant-vs-variable contract is defined for every input.
        if value is not None and math.isfinite(value):
            return z3.RealVal(value)
        if expr not in variables:
            variables[expr] = z3.Real(f"v::{expr}")
        return variables[expr]

    tracked = False
    for c in constraints:
        op = _OPS.get(c.kind)
        if op is None:
            continue
        solver.assert_and_track(op(term(c.left), term(c.right)), z3.Bool(c.id))
        tracked = True

    if not tracked:
        return FeasibilityResult(feasible=True, conflicting_ids=())

    result = solver.check()
    if result == z3.sat:
        return FeasibilityResult(feasible=True, conflicting_ids=())
    if result == z3.unsat:
        core = tuple(sorted(str(b) for b in solver.unsat_core()))
        return FeasibilityResult(feasible=False, conflicting_ids=core)
    # z3.unknown: do not claim feasibility we did not prove (honest abstention).
    raise RuntimeError("z3 returned 'unknown' for the constraint set")


def is_feasible(constraints: list[Constraint]) -> bool:
    """True iff the constraint set is globally satisfiable."""
    return check_feasibility(constraints).feasible


__all__ = ["FeasibilityResult", "check_feasibility", "is_feasible"]
