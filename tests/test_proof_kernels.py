"""Tests für die Proof-Kernel (Stein 2): echter Z3-QF_NRA-Kernel + Lean-Stub.

Z3 ist eine echte Entscheidungsprozedur fürs Polynom/Rational-Fragment (strenger als
sympy simplify). Nicht-Polynome (sin/cos/...) -> unsupported -> CAS-Fallback. Lean ist
nicht installiert -> Stub abstaint.
"""

import pytest
import sympy as sp

pytest.importorskip("z3", reason="z3-solver (optional [smt] extra) required for the Z3 proof kernel")

from gen.identity_research import AssumptionManifest, assess_identity
from gen.proof_kernels import LeanKernelStub, Z3IdentityKernel
from gen.ratification import SignOff
from gen.research_promotion import autonomous_stage, promote_to_established


def _vars():
    return {"x": "real", "y": "real"}


def test_z3_proves_polynomial_identity():
    k = Z3IdentityKernel()
    r = k.check(sp.sympify("(x + 1)**2"), sp.sympify("x**2 + 2*x + 1"),
                variables={"x": "real"}, domain_id="R")
    assert r.status == "proved"
    assert r.kernel == "z3_qfnra"


def test_z3_proves_two_variable_identity():
    k = Z3IdentityKernel()
    r = k.check(sp.sympify("(x + y)**2"), sp.sympify("x**2 + 2*x*y + y**2"),
                variables=_vars(), domain_id="R")
    assert r.status == "proved"


def test_z3_refutes_false_polynomial_with_counterexample():
    k = Z3IdentityKernel()
    r = k.check(sp.sympify("x**2"), sp.sympify("x**2 + 1"), variables={"x": "real"}, domain_id="R")
    assert r.status == "refuted"
    assert r.counterexample is not None


def test_z3_unsupported_on_transcendental():
    k = Z3IdentityKernel()
    r = k.check(sp.sympify("sin(x)"), sp.sympify("sin(x)"), variables={"x": "real"}, domain_id="R")
    assert r.status == "unsupported"


def test_z3_unsupported_with_predicates():
    k = Z3IdentityKernel()
    r = k.check(sp.sympify("x"), sp.sympify("x"), variables={"x": "real"}, domain_id="R",
                predicates=("x > 0",))
    assert r.status == "unsupported"


def test_lean_stub_always_abstains():
    r = LeanKernelStub().check(sp.sympify("x"), sp.sympify("x"), variables={"x": "real"}, domain_id="R")
    assert r.status == "unsupported"
    assert "no Lean" in r.detail


def test_assess_polynomial_is_z3_certified():
    art = assess_identity("binom", "(x + 1)**2", "x**2 + 2*x + 1",
                          AssumptionManifest(domain_id="R", variables={"x": "real"}))
    assert art.status == "SURVIVED_NOVEL"
    assert art.proof is not None
    assert art.proof.lean_status == "z3_certified"     # stronger than CAS for polynomials
    assert art.proof.method == "z3_qfnra"
    assert art.proof_tier == 3


def test_assess_trig_falls_back_to_cas():
    art = assess_identity("pyth", "sin(x)**2 + cos(x)**2", "1",
                          AssumptionManifest(domain_id="R", variables={"x": "real"}))
    assert art.proof.lean_status == "cas_certified"    # z3 unsupported on trig -> CAS proves it


def test_z3_certified_can_be_promoted_with_signoff():
    art = assess_identity("binom2", "(x + 1)**2", "x**2 + 2*x + 1",
                          AssumptionManifest(domain_id="R", variables={"x": "real"}))
    assert autonomous_stage(art) == "HARDENED"          # z3_certified reaches HARDENED
    rec = promote_to_established(art, SignOff(approved=frozenset({"binom2"}), approver="ozan"))
    assert rec is not None and rec.to_stage == "ESTABLISHED"
