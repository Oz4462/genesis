"""proof_loop — the math/geometry CERTIFICATION loop: propose -> numeric prefilter -> kernel proof.

The certifiable regime (FORSCHUNG_AUTONOMES_ERFINDEN §A3): unlike empirical physics, a mathematical
identity can be PROVEN — the kernel is the unbestechliche Richter. The loop, honest about what each layer
buys:

  1. NUMERIC PREFILTER (mpmath, high precision) — sample the claim at many points at ~50 digits. Numeric
     AGREEMENT is evidence, not proof (Ramanujan-machine lesson); numeric DISAGREEMENT is a cheap, sound
     REFUTER (sin(x)=x agrees to 1e-7 near 0 but |sin(1)-1|=0.16 at 50 digits — caught before any solver).
  2. SymPy simplify — a heuristic CAS layer (``simplify(lhs-rhs)==0``). It is UNSOUND about domain holes
     (it cancels ``(x²+x)/x`` to ``x+1``, hiding the x=0 hole), so a SymPy zero alone is only "Kandidat".
  3. KERNEL (z3 QF_NRA via ``proof_kernels.Z3IdentityKernel``) — a real decision procedure for the
     polynomial/rational fragment: proves ``∀ vars: lhs==rhs`` by ``Not(lhs==rhs)`` UNSAT, or REFUTES with
     a counterexample (it finds the x=0 hole SymPy hid). Only a kernel "proved" earns the label **"Satz"**.

Verdict labels (Entdecken≠Zertifizieren): **"Satz"** only kernel-closed; **"widerlegt"** when the prefilter
or the kernel refutes (with a counterexample where available); **"Kandidat"** when it agrees numerically and
SymPy/heuristics like it but no kernel could close it (e.g. transcendental nodes z3 cannot model — the Lean
slot ``LeanKernelStub`` is the future path); **"unsupported"** when it cannot even be parsed. A kernel proves
the STATEMENT, not the intent; numeric agreement is evidence, never proof. Deterministic, offline (z3+sympy+mpmath).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence

import mpmath as mp
import numpy as np
import sympy as sp

from ..proof_kernels import ProofKernel, Z3IdentityKernel

ProofStatus = Literal["Satz", "Kandidat", "widerlegt", "unsupported"]


@dataclass(frozen=True)
class IdentityClaim:
    """A proposed identity ``lhs == rhs`` over ``variables`` (name -> 'real'|'positive'|'integer') on a
    ``domain_id`` ('R'|'R+'|'N'). ``sample_lo/hi`` bound the numeric prefilter's sampling box."""

    lhs: str
    rhs: str
    variables: dict[str, str] = field(default_factory=lambda: {"x": "real"})
    domain_id: str = "R"
    sample_lo: float = -2.0
    sample_hi: float = 2.0


@dataclass(frozen=True)
class ProofVerdict:
    """Outcome: ``status`` ('Satz' only kernel-closed), whether the numeric prefilter agreed, which kernel
    decided, a human detail, and a counterexample dict when refuted by the kernel."""

    status: ProofStatus
    numeric_ok: bool
    kernel: str
    detail: str
    counterexample: Optional[dict] = None


def numeric_prefilter(claim: IdentityClaim, *, n_samples: int = 40, prec_dps: int = 50,
                      seed: int = 0) -> tuple[bool, float]:
    """High-precision numeric check: sample the variables in their box and compare ``lhs`` vs ``rhs`` at
    ~``prec_dps`` digits. Returns ``(agrees, worst_abs_diff)`` — ``agrees`` is False (a sound refutation)
    when the worst |lhs-rhs| exceeds the precision tolerance. Points that fail to evaluate (e.g. a sampled
    pole) are skipped; if none evaluate, it abstains (agrees=True) and leaves the verdict to the kernel."""
    mp.mp.dps = prec_dps
    tol = mp.mpf(10) ** (-(prec_dps // 2))
    try:
        names = list(claim.variables)
        syms = [sp.Symbol(n) for n in names]      # flat list -> lambdify makes f(*args) of len(names)
        lhs = sp.sympify(claim.lhs)
        rhs = sp.sympify(claim.rhs)
        f_lhs = sp.lambdify(syms, lhs, "mpmath")
        f_rhs = sp.lambdify(syms, rhs, "mpmath")
    except Exception:
        return True, 0.0
    rng = np.random.default_rng(seed)
    worst = mp.mpf(0)
    evaluated = 0
    for _ in range(n_samples):
        point = []
        for name in names:
            lo = max(claim.sample_lo, 1e-6) if claim.variables[name] == "positive" else claim.sample_lo
            point.append(mp.mpf(float(rng.uniform(lo, claim.sample_hi))))
        try:
            diff = abs(f_lhs(*point) - f_rhs(*point))
        except Exception:
            continue
        evaluated += 1
        if diff > worst:
            worst = diff
    if evaluated == 0:
        return True, 0.0
    return worst < tol, float(worst)


def prove_identity(claim: IdentityClaim, *, kernels: Sequence[ProofKernel] = (Z3IdentityKernel(),),
                   n_samples: int = 40, prec_dps: int = 50, seed: int = 0) -> ProofVerdict:
    """Run the certification loop. **"Satz"** only when a kernel proves it; **"widerlegt"** on numeric or
    kernel refutation; **"Kandidat"** on numeric+heuristic agreement without a kernel close; **"unsupported"**
    on a parse failure. Deterministic."""
    try:
        lhs = sp.sympify(claim.lhs)
        rhs = sp.sympify(claim.rhs)
    except Exception as exc:
        return ProofVerdict("unsupported", False, "parse", f"cannot parse the claim: {exc}")

    agrees, worst = numeric_prefilter(claim, n_samples=n_samples, prec_dps=prec_dps, seed=seed)
    if not agrees:
        return ProofVerdict("widerlegt", False, "mpmath",
                            f"numeric disagreement at {prec_dps} digits (worst |lhs-rhs| = {worst:.3g})")

    sympy_zero = sp.simplify(lhs - rhs) == 0  # heuristic only; UNSOUND about domain holes -> never "Satz" alone

    for kernel in kernels:
        result = kernel.check(lhs, rhs, variables=claim.variables, domain_id=claim.domain_id)
        if result.status == "proved":
            return ProofVerdict("Satz", True, result.kernel, result.detail)
        if result.status == "refuted":
            return ProofVerdict("widerlegt", True, result.kernel, result.detail,
                                counterexample=result.counterexample)

    detail = ("numeric agreement + SymPy simplify==0 (heuristic), but no kernel could close it"
              if sympy_zero else "numeric agreement, SymPy inconclusive, no kernel close")
    return ProofVerdict("Kandidat", True, "sympy" if sympy_zero else "mpmath", detail)
