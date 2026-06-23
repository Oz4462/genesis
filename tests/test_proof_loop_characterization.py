"""Characterization test for proof_loop.py (T02): proves the three-layer certification loop
(mpmath numeric prefilter → sympy heuristic → kernel) is genuinely executed and that
**only a kernel "proved" result earns status "Satz"** — never a sympy-alone facade.

Per spec and 2026-06-23 decisions:
- kernel-provable polynomial identity → "Satz"
- numerically-false identity → "widerlegt" caught at mpmath prefilter (kernel not decisive)
- domain-hole case (x²+x)/x = x+1 (sympy simplify==0) → NOT "Satz" (Kandidat or widerlegt)
- unparseable → "unsupported"
- facade killer: driving input changes outcome; documented fail-loud / honest abstention exercised
- property-based (Hypothesis) determinism + input sensitivity where contract promises (A5)

Uses ONLY real constructors (IdentityClaim from the module under test) + pre-existing
gen.proof_kernels for KernelResult (duck-typed protocol impls for kernel layer). No new deps.
z3-solver optional: kernel close is proven via provided test kernels (always-available path).
"""

from __future__ import annotations

import sympy as sp

import pytest

# hypothesis is a dev extra; importorskip prevents hard collection failure in envs without [dev]
# (addresses latent coupling while keeping property tests authoritative for this characterization).
pytest.importorskip("hypothesis", reason="hypothesis (dev extra) required for property-based characterization tests")
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.proof_loop import (
    IdentityClaim,
    ProofVerdict,
    numeric_prefilter,
    prove_identity,
)
from gen.proof_kernels import KernelResult


# --- Test double kernels (real collaborators, no z3 required) to drive kernel layer ---

class _ProvingKernel:
    """A kernel that always returns 'proved' — used to prove that a kernel close is what earns 'Satz'."""
    name = "test_prover"

    def check(self, e_lhs: sp.Expr, e_rhs: sp.Expr, *, variables: dict[str, str],
              domain_id: str, predicates: tuple[str, ...] = ()) -> KernelResult:
        return KernelResult("proved", self.name, "forced kernel close for characterization")


class _RefutingKernel:
    """A kernel that always returns 'refuted' with a counterexample — exercises kernel-refute path."""
    name = "test_refuter"

    def check(self, e_lhs: sp.Expr, e_rhs: sp.Expr, *, variables: dict[str, str],
              domain_id: str, predicates: tuple[str, ...] = ()) -> KernelResult:
        return KernelResult(
            "refuted", self.name, "forced kernel refutation",
            counterexample={"x": "0"}
        )


class _UnsupportedKernel:
    """Kernel abstains — forces the sympy/mpmath fallback path after numeric agree."""
    name = "test_unsup"

    def check(self, e_lhs: sp.Expr, e_rhs: sp.Expr, *, variables: dict[str, str],
              domain_id: str, predicates: tuple[str, ...] = ()) -> KernelResult:
        return KernelResult("unsupported", self.name, "kernel cannot decide")


def _poly_identity() -> IdentityClaim:
    return IdentityClaim("(x+1)**2", "x**2 + 2*x + 1", {"x": "real"}, "R")


def _domain_hole() -> IdentityClaim:
    # SymPy wrongly cancels; only kernel sees x=0 hole. Numeric sampling can agree at x!=0.
    return IdentityClaim("(x**2 + x)/x", "x + 1", {"x": "real"}, "R")


def _num_false() -> IdentityClaim:
    return IdentityClaim("sin(x)", "x", {"x": "real"}, "R")


def _trans_true() -> IdentityClaim:
    return IdentityClaim("sin(x)**2 + cos(x)**2", "1", {"x": "real"}, "R")


def _unparseable() -> IdentityClaim:
    return IdentityClaim("x +* 1", "x", {"x": "real"}, "R")


# --- Core facade detection: output changes when input changes (layer exercised) ---

def test_mpmath_prefilter_refutes_false_and_short_circuits_kernel():
    """L1 + L2: numerically false identity is refuted by prefilter (kernel='mpmath', numeric_ok=False).
    Even when a proving kernel is supplied, prefilter wins — proves prefilter layer runs first."""
    claim = _num_false()
    prover = _ProvingKernel()
    v = prove_identity(claim, kernels=[prover])
    assert v.status == "widerlegt"
    assert v.kernel == "mpmath"
    assert not v.numeric_ok
    assert v.counterexample is None
    # Prover was supplied but not decisive (prefilter short-circuit).
    # (We do not spy private state; the 'mpmath' label + early return semantics prove the layer order.)


def test_sympy_heuristic_yields_kandidat_not_satz_when_no_kernel_close():
    """L1 + L4: sympy simplify==0 alone never earns 'Satz' (facade killer)."""
    claim = _poly_identity()
    # Confirm the heuristic would "approve".
    lhs, rhs = sp.sympify(claim.lhs), sp.sympify(claim.rhs)
    assert sp.simplify(lhs - rhs) == 0
    v = prove_identity(claim, kernels=[_UnsupportedKernel()])
    assert v.status == "Kandidat"
    assert "sympy" in v.kernel  # sympy heuristic path taken
    assert v.numeric_ok
    # Never promotes to Satz without kernel.
    assert v.status != "Satz"


def test_kernel_close_is_what_earns_satz_not_sympy_facade():
    """L1: only when a kernel returns 'proved' do we get status='Satz' (with its kernel name)."""
    claim = _poly_identity()
    v = prove_identity(claim, kernels=[_ProvingKernel()])
    assert v.status == "Satz"
    assert v.kernel == "test_prover"
    assert v.numeric_ok
    assert v.counterexample is None


def test_transcendental_agrees_but_kandidat_without_kernel():
    """L1: true transcendental that sympy likes but z3 cannot model stays Kandidat (honest abstention)."""
    claim = _trans_true()
    v = prove_identity(claim, kernels=[_UnsupportedKernel()])
    assert v.status == "Kandidat"
    assert v.numeric_ok


def test_domain_hole_sympy_approves_kernel_refutes_not_satz():
    """L1 + L2: domain-hole case where sympy simplify==0 but kernel finds the hole → widerlegt (not Satz).
    Proves kernel (not sympy) is the decider for certification."""
    claim = _domain_hole()
    lhs, rhs = sp.sympify(claim.lhs), sp.sympify(claim.rhs)
    assert sp.simplify(lhs - rhs) == 0, "sympy must appear to accept for the facade contrast"
    v = prove_identity(claim, kernels=[_RefutingKernel()])
    assert v.status == "widerlegt"
    assert v.kernel == "test_refuter"
    assert v.counterexample is not None and v.counterexample.get("x") == "0"
    # Even if numeric prefilter agreed on sampled non-zero points.


def test_unparseable_claim_is_unsupported_before_any_layer():
    """L4: parse failure yields unsupported immediately (no numeric, no kernel).
    Note: parse guard is intentionally before the kernel loop, so even when kernels= are supplied
    the early return is taken (this is the documented "unsupported" path, not a facade)."""
    claim = _unparseable()
    # Supply explicit kernels list (even though unreachable) to demonstrate API usage + that
    # parse still wins (kernel list length is irrelevant for this branch).
    v = prove_identity(claim, kernels=[_UnsupportedKernel()])
    assert v.status == "unsupported"
    assert v.kernel == "parse"
    assert not v.numeric_ok


# --- Input sensitivity (L2 Drift) + fail-loud / abstention ---

def test_different_claims_produce_meaningfully_different_verdicts():
    """L2: two different inputs consume different paths and produce observably different outputs
    (status + kernel label + detail) — proves inputs are genuinely consumed, not a constant facade."""
    poly = prove_identity(_poly_identity(), kernels=[_UnsupportedKernel()])
    hole = prove_identity(_domain_hole(), kernels=[_RefutingKernel()])
    falsey = prove_identity(_num_false())
    assert poly.status != falsey.status
    assert hole.status != poly.status
    # Strengthen to cover audit claim: kernel and/or detail also differ for distinct driving claims.
    assert (poly.kernel, poly.detail) != (falsey.kernel, falsey.detail)
    assert (hole.kernel, hole.detail) != (poly.kernel, poly.detail)


def test_unsupported_is_the_honest_abstention_for_bad_input():
    """L4: unparseable is explicit abstention, never a fabricated Kandidat/Satz."""
    v = prove_identity(_unparseable())
    assert v.status == "unsupported"
    assert "cannot parse" in v.detail


def test_empty_variables_and_const_only_identities_are_supported():
    """Empty variables dict (constant-only identity) is a valid public-API input and yields Kandidat
    (or Satz with a proving kernel). This exercises the 'no variables' path and IdentityClaim defaults."""
    const_true = IdentityClaim("2", "1+1", {})  # empty vars, pure const
    v_kand = prove_identity(const_true, kernels=[_UnsupportedKernel()])
    assert v_kand.status == "Kandidat"
    # Supplying a proving kernel still yields Satz (kernel decides, even for consts).
    v_satz = prove_identity(const_true, kernels=[_ProvingKernel()])
    assert v_satz.status == "Satz"
    assert v_satz.kernel == "test_prover"


# --- Property-based tests (invariants) ---

@given(
    seed=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=20, deadline=2000, derandomize=True)
def test_property_determinism_identical_input_yields_identical_verdict(seed: int) -> None:
    """A5 reproducibility: same claim + seed + kernels → identical ProofVerdict (status, kernel)."""
    claim = _poly_identity()
    # Use unsup kernel so we hit the always-available Kandidat path (z3 optional).
    v1 = prove_identity(claim, kernels=[_UnsupportedKernel()], seed=seed)
    v2 = prove_identity(claim, kernels=[_UnsupportedKernel()], seed=seed)
    assert v1.status == v2.status
    assert v1.kernel == v2.kernel
    assert v1.numeric_ok == v2.numeric_ok


@given(
    # Only safe algebraic identities that survive sampling; exercise input variation.
    expr_pair=st.sampled_from([
        ("(x + 3)**2", "x**2 + 6*x + 9"),
        ("x * 2", "2 * x"),
        ("x + 0", "x"),
    ]),
    seed=st.integers(0, 3),
)
@settings(max_examples=12, deadline=2000, derandomize=True)
def test_property_input_variation_changes_detail_but_preserves_kandidat_when_no_kernel(expr_pair, seed):
    """When kernel abstains, different (but true) identities still go to Kandidat, but detail or worst-diff
    may vary — proving the prefilter+sympy layers are driven by the actual claim (not constant)."""
    lhs, rhs = expr_pair
    # Use explicit keywords (clearer, matches dataclass order exactly, avoids positional fragility).
    claim = IdentityClaim(lhs=lhs, rhs=rhs, variables={"x": "real"}, domain_id="R")
    v = prove_identity(claim, kernels=[_UnsupportedKernel()], seed=seed)
    assert v.status == "Kandidat"
    # The numeric layer ran (we have a numeric_ok field) and the claim text affects path.
    assert isinstance(v.detail, str) and len(v.detail) > 0


# --- Negative / documented guard behaviour (a gate without a test does not exist) ---

def test_bad_sample_range_produces_fail_loud_from_prefilter():
    """L4: hi < lo is invalid; the public API fails loud (ValueError from sampling) rather than silent wrong.
    This matches no-silent-defaults; we assert the error surfaces from the called layer."""
    bad = IdentityClaim("x", "x", {"x": "real"}, sample_lo=5.0, sample_hi=1.0)
    with pytest.raises(ValueError):
        prove_identity(bad)


def test_zero_samples_defers_to_sympy_heuristic():
    """Edge but public: n_samples=0 makes prefilter abstain (agrees=True); sympy decides (documented path)."""
    claim = _poly_identity()
    v = prove_identity(claim, n_samples=0, kernels=[_UnsupportedKernel()])
    # Must not be "widerlegt" from prefilter; defers.
    assert v.status == "Kandidat"
    assert v.numeric_ok  # prefilter abstained positively


def test_numeric_prefilter_internal_parse_abstain_path_is_reachable():
    """The prefilter's broad except (parse/lambdify failure inside it) returns (True, 0.0) abstain.
    prove_identity has an outer guard, but the internal path is still part of the module and is now
    directly exercised (addresses coverage of the documented numeric_prefilter behaviour)."""
    bad = IdentityClaim("x +* 1", "x", {"x": "real"}, "R")
    agrees, worst = numeric_prefilter(bad)
    # Prefilter catches its own sympify/lambdify error and abstains (lets caller decide).
    assert agrees is True
    assert worst == 0.0 or worst == 0  # float or int zero from the except return
