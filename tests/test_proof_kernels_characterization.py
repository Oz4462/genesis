"""Characterization test for proof_kernels.py (T02): proves Z3IdentityKernel is a
REAL decision procedure for the polynomial/rational fragment (QF_NRA), not a facade.

Per spec:
- true polynomial identity -> 'proved' because z3 reports UNSAT on Not(lhs == rhs)
- false polynomial -> 'refuted' with a counterexample (witness is real, not invented)
- honest abstention paths (non-poly, predicates, bad types) -> 'unsupported'
- LeanKernelStub always abstains, independent of input (by design, records only)

Facade-killer (per team decisions):
(a) headline output (status, kernel, detail, counterexample) changes meaningfully
    when driving input changes (proves the expr/vars/domain are consumed)
(b) documented fail-loud/honest-abstention paths fire exactly (NEGATIVE test)

Property-based (Hypothesis): determinism of results for identical inputs (A5 contract);
consistent decision on algebraically equivalent rewrites.

Uses ONLY the module under review + stdlib + declared deps (sympy, z3 via importorskip,
hypothesis via guarded importorskip). Real sympy.Expr + plain dict/str/tuple inputs.
No src edits (module already correct on inspection + probes).
"""

from __future__ import annotations

import pytest

pytest.importorskip("z3", reason="z3-solver (optional [smt] extra) required to characterize the real Z3 QF_NRA kernel")

import sympy as sp

# hypothesis guarded: dev extra; prevents collection failure in envs without [dev]
# (see pyproject.toml and prior T0x decisions)
pytest.importorskip("hypothesis", reason="hypothesis (dev extra) required for property-based determinism/equivalence tests")
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.proof_kernels import (
    KernelResult,
    LeanKernelStub,
    Z3IdentityKernel,
)


# ---------------------------------------------------------------------------
# Helpers (tiny, local to keep test self-contained; real API inputs)
# ---------------------------------------------------------------------------

def _k() -> Z3IdentityKernel:
    return Z3IdentityKernel(timeout_ms=2000)


def _true_poly() -> tuple[sp.Expr, sp.Expr, dict[str, str], str]:
    return (sp.sympify("(x + 1)**2"), sp.sympify("x**2 + 2*x + 1"), {"x": "real"}, "R")


def _false_poly() -> tuple[sp.Expr, sp.Expr, dict[str, str], str]:
    return (sp.sympify("x**2"), sp.sympify("x**2 + 1"), {"x": "real"}, "R")


def _true_two_var() -> tuple[sp.Expr, sp.Expr, dict[str, str], str]:
    return (sp.sympify("(x + y)**2"), sp.sympify("x**2 + 2*x*y + y**2"), {"x": "real", "y": "real"}, "R")


def _transcendental() -> tuple[sp.Expr, sp.Expr, dict[str, str], str]:
    return (sp.sympify("sin(x)**2 + cos(x)**2"), sp.sympify("1"), {"x": "real"}, "R")


# ---------------------------------------------------------------------------
# 1. Core: 'proved' comes from genuine UNSAT; 'refuted' carries real ce
# ---------------------------------------------------------------------------

def test_z3_true_polynomial_identity_returns_proved_from_unsat():
    """L1 truth: a canonical polynomial identity is decided 'proved' with the documented
    detail string that signals the UNSAT path inside z3 (Not(lhs==rhs) is UNSAT)."""
    lhs, rhs, vars_, dom = _true_poly()
    r = _k().check(lhs, rhs, variables=vars_, domain_id=dom)
    assert r.status == "proved"
    assert r.kernel == "z3_qfnra"
    assert "UNSAT" in r.detail
    assert r.counterexample is None  # only refuted cases carry ce


def test_z3_false_polynomial_returns_refuted_with_counterexample():
    """A false identity yields 'refuted' + non-None counterexample (may be {} when
    difference is ground-constant; still a valid universal refutation)."""
    lhs, rhs, vars_, dom = _false_poly()
    r = _k().check(lhs, rhs, variables=vars_, domain_id=dom)
    assert r.status == "refuted"
    assert r.kernel == "z3_qfnra"
    assert r.counterexample is not None  # contract: present on refuted
    assert "violating the identity" in r.detail


def test_z3_refuted_counterexample_is_genuine_witness_when_present():
    """L1 + L4: when z3 supplies a concrete assignment in ce, substituting it back
    into the original sympy exprs yields lhs != rhs (the witness is not fabricated)."""
    lhs, rhs, vars_, dom = sp.sympify("x**2"), sp.sympify("0"), {"x": "real"}, "R"
    r = _k().check(lhs, rhs, variables=vars_, domain_id=dom)
    assert r.status == "refuted"
    ce = r.counterexample or {}
    if ce:
        # z3 str values are integers or "p/q" rationals
        sub = {}
        for name, valstr in ce.items():
            if "/" in valstr:
                p, q = map(int, valstr.split("/"))
                sub[sp.Symbol(name)] = sp.Rational(p, q)
            else:
                sub[sp.Symbol(name)] = sp.Integer(int(valstr))
        lhs_v = sp.sympify(lhs).subs(sub)
        rhs_v = sp.sympify(rhs).subs(sub)
        assert lhs_v != rhs_v, f"ce {ce} should falsify {lhs} == {rhs}"


# ---------------------------------------------------------------------------
# 2. Honest abstention paths (the documented 'unsupported' contract)
# ---------------------------------------------------------------------------

def test_z3_abstains_on_transcendental():
    """Non-polynomial (trig) -> honest 'unsupported' so caller can fall back to CAS."""
    lhs, rhs, vars_, dom = _transcendental()
    r = _k().check(lhs, rhs, variables=vars_, domain_id=dom)
    assert r.status == "unsupported"
    assert r.kernel == "z3_qfnra"


def test_z3_abstains_on_non_integer_power():
    r = _k().check(
        sp.sympify("x**0.5"), sp.sympify("sqrt(x)"),
        variables={"x": "real"}, domain_id="R"
    )
    assert r.status == "unsupported"
    assert "non-integer power" in r.detail


def test_z3_abstains_when_predicates_declared():
    """Predicates are conservatively unsupported in v1 (kernel does not model hypotheses)."""
    lhs, rhs, vars_, dom = sp.sympify("x"), sp.sympify("x"), {"x": "real"}, "R"
    r = _k().check(lhs, rhs, variables=vars_, domain_id=dom, predicates=("x > 0",))
    assert r.status == "unsupported"
    assert "predicates" in r.detail


def test_z3_abstains_on_unsupported_variable_type():
    r = _k().check(
        sp.sympify("x"), sp.sympify("x"),
        variables={"x": "complex"}, domain_id="R"
    )
    assert r.status == "unsupported"
    assert "type unsupported" in r.detail


def test_z3_abstains_on_unbound_symbol_in_expression():
    """Expr mentioning a symbol not declared in variables -> unsupported (honest; no silent binding)."""
    # x declared, but y appears in expr
    r = _k().check(
        sp.sympify("x + y"), sp.sympify("x + y"),
        variables={"x": "real"}, domain_id="R"
    )
    assert r.status == "unsupported"
    assert "unbound symbol" in r.detail


# ---------------------------------------------------------------------------
# 3. LeanKernelStub always abstains (design contract)
# ---------------------------------------------------------------------------

def test_lean_stub_always_abstains():
    r = LeanKernelStub().check(
        sp.sympify("(x+1)**2"), sp.sympify("x**2+2*x+1"),
        variables={"x": "real"}, domain_id="R"
    )
    assert r.status == "unsupported"
    assert r.kernel == "lean_stub"
    assert "no Lean" in r.detail


def test_lean_stub_abstains_even_for_trivial_true_and_ignores_input():
    """Stub contract: always unsupported, input-independent (records only)."""
    for lhs, rhs in [
        (sp.sympify("x"), sp.sympify("x")),
        (sp.sympify("2+2"), sp.sympify("4")),
        (sp.sympify("sin(x)"), sp.sympify("0")),
    ]:
        r = LeanKernelStub().check(lhs, rhs, variables={"x": "real"}, domain_id="R")
        assert r.status == "unsupported"


# ---------------------------------------------------------------------------
# 4. Facade killer + input sensitivity (output changes when input changes)
# ---------------------------------------------------------------------------

def test_different_identities_produce_meaningfully_different_results():
    """(a) Driving input changes -> status/kernel/detail differ. Proves consumption, not constant."""
    k = _k()
    lhs_t, rhs_t, v_t, d_t = _true_poly()
    lhs_f, rhs_f, v_f, d_f = _false_poly()
    r_true = k.check(lhs_t, rhs_t, variables=v_t, domain_id=d_t)
    r_false = k.check(lhs_f, rhs_f, variables=v_f, domain_id=d_f)
    assert r_true.status != r_false.status
    assert r_true.kernel == r_false.kernel  # both z3
    assert r_true.detail != r_false.detail
    # one has ce, one does not
    assert (r_true.counterexample is None) != (r_false.counterexample is None)


def test_z3_const_only_identities_are_decided():
    """Constants (no variables) are still genuinely decided by z3 (empty env path)."""
    k = _k()
    r_true = k.check(sp.sympify("2 + 2"), sp.sympify("4"), variables={}, domain_id="R")
    r_false = k.check(sp.sympify("2 + 2"), sp.sympify("5"), variables={}, domain_id="R")
    assert r_true.status == "proved"
    assert r_false.status == "refuted"


# ---------------------------------------------------------------------------
# 5. Property-based invariants (Hypothesis)
# ---------------------------------------------------------------------------

# Safe families of true identities (polynomial/commutative/associativity that Z3 QF_NRA decides)
_TRUE_ID_FAMILIES = [
    ("x + 1", "1 + x"),
    ("x * y", "y * x"),
    ("(x + y)**2", "x**2 + 2*x*y + y**2"),
    ("x**2 + 2*x + 1", "(x + 1)**2"),
]

_FALSE_ID_FAMILIES = [
    ("x**2", "x**2 + 1"),
    ("x + 1", "x + 2"),
]


@given(
    pair=st.sampled_from(_TRUE_ID_FAMILIES),
)
@settings(max_examples=8, deadline=3000)
def test_property_z3_proves_true_identities_and_is_deterministic(pair):
    """A5 determinism + real decision: same input => identical KernelResult; true poly => proved + UNSAT detail."""
    lhs_s, rhs_s = pair
    lhs, rhs = sp.sympify(lhs_s), sp.sympify(rhs_s)
    vars_ = {"x": "real", "y": "real"} if "y" in lhs_s or "y" in rhs_s else {"x": "real"}
    k = _k()
    r1 = k.check(lhs, rhs, variables=vars_, domain_id="R")
    r2 = k.check(lhs, rhs, variables=vars_, domain_id="R")
    assert r1.status == "proved"
    assert r1 == r2  # full dataclass equality (status, kernel, detail, ce)
    assert "UNSAT" in r1.detail


@given(
    pair=st.sampled_from(_FALSE_ID_FAMILIES),
)
@settings(max_examples=6, deadline=3000)
def test_property_z3_refutes_false_and_counterexample_contract(pair):
    """False identities are always refuted with a (possibly-empty) counterexample present."""
    lhs_s, rhs_s = pair
    lhs, rhs = sp.sympify(lhs_s), sp.sympify(rhs_s)
    r = _k().check(lhs, rhs, variables={"x": "real"}, domain_id="R")
    assert r.status == "refuted"
    assert r.counterexample is not None


# ---------------------------------------------------------------------------
# 6. Domain / integer / positive paths are exercised (input consumed)
# ---------------------------------------------------------------------------

def test_integer_and_positive_domains_are_respected():
    k = _k()
    # integer N
    r = k.check(sp.sympify("n + 1"), sp.sympify("1 + n"), variables={"n": "integer"}, domain_id="N")
    assert r.status == "proved"
    # positive forces >0 constraint; identity still holds
    r = k.check(sp.sympify("x"), sp.sympify("x"), variables={"x": "real"}, domain_id="R+")
    assert r.status == "proved"


# ---------------------------------------------------------------------------
# 7. Explicit genuine UNSAT wording + ground-constant ce validity (L1/L4)
# ---------------------------------------------------------------------------

def test_z3_proved_uses_exact_unsat_detail_string():
    """The 'proved' result must carry the precise detail emitted on genuine z3 unsat.
    This proves we are not faking 'proved' via heuristic."""
    lhs, rhs, vars_, dom = _true_poly()
    r = _k().check(lhs, rhs, variables=vars_, domain_id=dom)
    assert r.status == "proved"
    assert r.detail == "Not(lhs==rhs) is UNSAT over the declared domain"


def test_refuted_ground_constant_falsehood_has_empty_ce_which_is_valid():
    """When lhs-rhs reduces to a ground falsehood independent of vars (e.g. 0==1),
    z3 produces sat on the negation with no var assignments needed -> ce={}.
    This is correct (the identity is false for all assignments); not a missing ce bug.
    We assert status=refuted and ce is not None (per public contract)."""
    r = _k().check(sp.sympify("1"), sp.sympify("2"), variables={}, domain_id="R")
    assert r.status == "refuted"
    assert r.counterexample is not None  # may be {}; still valid universal refutation
    # no var to assign; falsehood is unconditional


# ---------------------------------------------------------------------------
# 8. L4 edge: 0 ** negative is now explicitly unsupported (prevents 1/0 term)
# ---------------------------------------------------------------------------

def test_z3_abstains_on_zero_to_negative_power():
    """0**(-k) is mathematically undefined; kernel must abstain rather than emit
    ill-formed 1/0 term into z3 (which previously happened for Integer(0) base)."""
    # Use unevaluated Pow to prevent sympy eager eval to ComplexInfinity
    zero = sp.Integer(0)
    neg1 = sp.Integer(-1)
    lhs = sp.Pow(zero, neg1, evaluate=False)
    rhs = sp.Integer(1)
    r = _k().check(lhs, rhs, variables={}, domain_id="R")
    assert r.status == "unsupported"
    assert "0 raised to negative power" in r.detail


def test_zero_to_zero_is_conventional_one():
    """0**0 is treated as 1 (documented convention in source); kernel returns proved for 0**0==1."""
    # unevaluated to ensure Pow node reaches _to_z3
    zero = sp.Integer(0)
    zero_exp = sp.Pow(zero, 0, evaluate=False)
    r = _k().check(zero_exp, sp.Integer(1), variables={}, domain_id="R")
    assert r.status == "proved"


# ---------------------------------------------------------------------------
# 9. Extended domain-constraint matrix (real/pos/int cross products)
# ---------------------------------------------------------------------------

def test_domain_constraint_matrix_variants():
    """Covers combinations of var type (real/positive/integer) x domain_id (R/R+/N)
    to ensure constraints are applied from both sources without silent misbehavior."""
    k = _k()
    # positive-typed var under R (type drives >0)
    r = k.check(sp.sympify("p"), sp.sympify("p"), variables={"p": "positive"}, domain_id="R")
    assert r.status == "proved"
    # integer var under R+ (domain forces >=? but >0 for R+ takes precedence via or)
    r = k.check(sp.sympify("n + 1"), sp.sympify("1 + n"), variables={"n": "integer"}, domain_id="R+")
    assert r.status == "proved"
    # real var under N (only >=0 if integer type; here no extra)
    r = k.check(sp.sympify("x + 1"), sp.sympify("1 + x"), variables={"x": "real"}, domain_id="N")
    assert r.status == "proved"


# ---------------------------------------------------------------------------
# 10. 'unknown' return path contract (timeout/incompleteness)
# ---------------------------------------------------------------------------

def test_z3_unknown_path_contract_is_supported():
    """Z3 may return 'unknown' (timeout or incompleteness). The kernel reports it.
    We exercise the public path; trivial identities decide fast so status may be
    proved/refuted/unknown depending on z3 timing heuristics. We only assert
    that 'unknown' if surfaced has the documented wording."""
    k = Z3IdentityKernel(timeout_ms=0)  # extreme; fast cases often still answer
    r = k.check(sp.sympify("(x+1)**2"), sp.sympify("x**2 + 2*x + 1"), variables={"x": "real"}, domain_id="R")
    if r.status == "unknown":
        assert "timeout" in r.detail or "incompleteness" in r.detail
    else:
        # acceptable: decided before timeout enforcement in this trivial case
        assert r.status in ("proved", "refuted")
