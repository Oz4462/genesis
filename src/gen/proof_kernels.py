"""Pluggable proof kernels for the math-research branch (stone 2, dual-agent locked).

A ProofKernel attempts a RIGOROUS proof of an identity ``lhs == rhs``. Two are provided:

- ``Z3IdentityKernel``: a REAL decision procedure for the polynomial/rational fragment over
  reals/integers (QF_NRA). It proves ``forall vars: lhs == rhs`` by checking that
  ``Not(lhs == rhs)`` is UNSAT under the declared domain — strictly stronger than sympy's
  heuristic ``simplify``. Non-polynomial nodes (sin/cos/exp/sqrt/...) are 'unsupported' so
  the caller falls back to CAS. Conservative: if predicates are declared it returns
  'unsupported' (it does not model arbitrary hypotheses in v1).
- ``LeanKernelStub``: records the statement and returns 'unsupported' — a real Lean/Coq
  kernel is not installed on this machine (years out); the adapter slot is ready.

This module imports only z3 + sympy (never identity_research) to avoid an import cycle:
callers pass primitive manifest fields (variables/domain_id/predicates).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Protocol, runtime_checkable

import sympy as sp

try:
    import z3
    _HAS_Z3 = True
except Exception:  # pragma: no cover - exercised only without the z3 extra
    z3 = None  # type: ignore
    _HAS_Z3 = False

KernelStatus = Literal["proved", "refuted", "unknown", "unsupported"]


@dataclass(frozen=True)
class KernelResult:
    status: KernelStatus
    kernel: str
    detail: str
    counterexample: Optional[dict] = None


@runtime_checkable
class ProofKernel(Protocol):
    name: str

    def check(self, e_lhs: sp.Expr, e_rhs: sp.Expr, *,
              variables: dict[str, str], domain_id: str, predicates: tuple[str, ...] = ()) -> KernelResult: ...


class _Z3Unsupported(Exception):
    pass


def _to_z3(expr: sp.Expr, env: dict):
    """Translate a sympy expression into a z3 arithmetic term (polynomial/rational only).
    Raises _Z3Unsupported on any non-polynomial node so the caller abstains honestly."""
    if expr.is_Integer:
        return z3.RealVal(int(expr))
    if expr.is_Rational:
        return z3.Q(int(expr.p), int(expr.q))
    if expr.is_Symbol:
        # key by NAME (string): sympy symbols carry assumptions, so Symbol('x', real=True)
        # != Symbol('x'); name-keying avoids that mismatch with the parsed expression.
        if expr.name in env:
            return env[expr.name]
        raise _Z3Unsupported(f"unbound symbol {expr}")
    if expr.is_Add:
        acc = z3.RealVal(0)
        for a in expr.args:
            acc = acc + _to_z3(a, env)
        return acc
    if expr.is_Mul:
        acc = z3.RealVal(1)
        for a in expr.args:
            acc = acc * _to_z3(a, env)
        return acc
    if expr.is_Pow:
        e = expr.exp
        if e.is_Integer:
            n = int(e)
            base = _to_z3(expr.base, env)
            if n == 0:
                return z3.RealVal(1)
            if n > 0:
                acc = base
                for _ in range(n - 1):
                    acc = acc * base
                return acc
            acc = base
            for _ in range(-n - 1):
                acc = acc * base
            return z3.RealVal(1) / acc
        raise _Z3Unsupported(f"non-integer power {e}")
    raise _Z3Unsupported(f"non-polynomial node {expr.func}")


class Z3IdentityKernel:
    """Real QF_NRA decision procedure for polynomial/rational identities."""

    name = "z3_qfnra"

    def __init__(self, timeout_ms: int = 4000) -> None:
        self.timeout_ms = timeout_ms

    def check(self, e_lhs: sp.Expr, e_rhs: sp.Expr, *,
              variables: dict[str, str], domain_id: str, predicates: tuple[str, ...] = ()) -> KernelResult:
        if not _HAS_Z3:
            return KernelResult("unsupported", self.name, "z3 not installed")
        if predicates:
            return KernelResult("unsupported", self.name, "declared predicates not modelled in v1")
        if any(t not in ("real", "positive", "integer") for t in variables.values()):
            return KernelResult("unsupported", self.name, "non-real/integer variable type unsupported")
        env = {n: (z3.Int(n) if t == "integer" else z3.Real(n)) for n, t in variables.items()}
        constraints = []
        for n, t in variables.items():
            if t == "positive" or domain_id == "R+":
                constraints.append(env[n] > 0)
            if domain_id == "N" and t == "integer":
                constraints.append(env[n] >= 0)
        try:
            zl, zr = _to_z3(e_lhs, env), _to_z3(e_rhs, env)
        except _Z3Unsupported as exc:
            return KernelResult("unsupported", self.name, str(exc))
        solver = z3.Solver()
        solver.set("timeout", self.timeout_ms)
        for c in constraints:
            solver.add(c)
        solver.add(z3.Not(zl == zr))
        res = solver.check()
        if res == z3.unsat:
            return KernelResult("proved", self.name, "Not(lhs==rhs) is UNSAT over the declared domain")
        if res == z3.sat:
            model = solver.model()
            ce = {n: str(model[env[n]]) for n in variables if model[env[n]] is not None}
            return KernelResult("refuted", self.name, "found an assignment violating the identity", counterexample=ce)
        return KernelResult("unknown", self.name, "z3 returned unknown (timeout/incompleteness)")


class LeanKernelStub:
    """Adapter slot for a real Lean/Coq kernel. None is installed on this machine, so it
    always abstains (records the statement). Wiring a real kernel later needs no contract change."""

    name = "lean_stub"

    def check(self, e_lhs: sp.Expr, e_rhs: sp.Expr, *,
              variables: dict[str, str], domain_id: str, predicates: tuple[str, ...] = ()) -> KernelResult:
        return KernelResult("unsupported", self.name, "no Lean/Coq kernel installed — statement recorded only")
