"""Characterization / facade-detector tests for ``gen.identity_research``.

Spec headline (depth-audit T05): the identity verifier is deterministic + LLM-free and
its TRUTH is produced by DEDUCTION (``prove_identity``: a real kernel or CAS establishes
``simplify(lhs-rhs)==0``) or by FALSIFICATION (``falsify``: a deterministic grid finds no
counterexample). Data/grid-consistency is a GATE, never a proof on its own; a false
identity is REFUTED with a CONCRETE counterexample witness, and ``assess_identity`` yields
an honest status + severity that never falsely merges two different claims.

Every test here is a real facade-detector — it asserts EITHER that the headline output
changes MEANINGFULLY when a driving input changes (the input is genuinely consumed, not a
canned constant) OR that a documented fail-loud / abstention path fires exactly. The legacy
``test_identity_research.py`` stays untouched; this file is the authoritative audit signal.

Verdict on inspection + these tests: REAL (no source defect exposed). See
``docs/audit/DEPTH_AUDIT_identity_research.md``.
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.identity_research import (
    AssumptionManifest,
    FalsificationReceipt,
    ProofCertificate,
    _lean_statement,
    _make_symbols,
    _parse,
    assess_identity,
    falsify,
    fingerprint,
    prove_identity,
)


def _mR(**vars_):
    """Real-domain manifest helper (default single real var ``x``)."""
    return AssumptionManifest(domain_id="R", variables=vars_ or {"x": "real"})


def _residual_at_witness(lhs: str, rhs: str, manifest: AssumptionManifest, witness: dict) -> float:
    """Re-evaluate ``lhs-rhs`` numerically at the reported witness — an INDEPENDENT check
    that the witness really is a counterexample (not just a tag the code attached)."""
    syms = _make_symbols(manifest)
    diff = _parse(lhs, syms) - _parse(rhs, syms)
    val = diff.subs({syms[n]: v for n, v in witness.items()})
    return float(val)


# ---------------------------------------------------------------------------
# 1. DEDUCTION: prove_identity establishes truth, and the grid is a GATE on it.
# ---------------------------------------------------------------------------

def test_prove_identity_deductively_proves_true_polynomial():
    """A true polynomial identity is DEDUCTIVELY proved (kernel or CAS), with a concrete
    cas_check string — not merely 'survived a grid'."""
    m = _mR(x="real")
    syms = _make_symbols(m)
    lhs, rhs = _parse("(x+1)**2", syms), _parse("x**2 + 2*x + 1", syms)
    cert = prove_identity(lhs, rhs, m, grid_passed=True, lean_statement=_lean_statement("(x+1)**2", "x**2+2*x+1", m))
    assert isinstance(cert, ProofCertificate)
    assert cert.deductively_proved is True
    assert cert.method in ("z3_qfnra", "cas_simplify", "cas_equals")
    assert cert.lean_status in ("z3_certified", "cas_certified")
    # honest about epistemic status: CAS/Z3 here is NOT a Lean-kernel proof
    assert "Lean" in cert.notes or cert.method == "z3_qfnra"


def test_prove_identity_grid_is_a_gate_not_bypassed():
    """Headline: data/grid-consistency is a GATE. Even a TRUE identity yields NO proof when
    the grid did not pass — proof is refused, never fabricated (keine stillen Defaults)."""
    m = _mR(x="real")
    syms = _make_symbols(m)
    lhs, rhs = _parse("(x+1)**2", syms), _parse("x**2 + 2*x + 1", syms)
    cert = prove_identity(lhs, rhs, m, grid_passed=False, lean_statement="stmt")
    assert cert.deductively_proved is False
    assert cert.method == "none"
    assert cert.lean_status == "admitted"


def test_prove_identity_does_not_prove_a_false_identity():
    """A genuinely false identity is NEVER reported as deductively proved (no false merge)."""
    m = _mR(x="real")
    syms = _make_symbols(m)
    lhs, rhs = _parse("x**2", syms), _parse("x", syms)
    cert = prove_identity(lhs, rhs, m, grid_passed=True, lean_statement="stmt")
    assert cert.deductively_proved is False


def test_prove_identity_kernel_outranks_cas_for_polynomials():
    """Driving-input depth: a polynomial identity (z3's QF_NRA fragment) is decided by the
    real KERNEL, while a trig identity (outside that fragment) falls back to CAS. Proves the
    method is chosen from the *content*, not hardcoded. Requires the optional z3 extra."""
    pytest.importorskip("z3")
    m = _mR(x="real")
    syms = _make_symbols(m)
    poly = prove_identity(_parse("(x+1)**2", syms), _parse("x**2+2*x+1", syms),
                          m, grid_passed=True, lean_statement="s")
    trig = prove_identity(_parse("sin(x)**2+cos(x)**2", syms), _parse("1", syms),
                          m, grid_passed=True, lean_statement="s")
    assert poly.method == "z3_qfnra" and poly.lean_status == "z3_certified"
    assert trig.deductively_proved is True and trig.method != "z3_qfnra"


# ---------------------------------------------------------------------------
# 2. FALSIFICATION: a false identity is REFUTED with a GENUINE witness.
# ---------------------------------------------------------------------------

def test_falsify_survives_true_identity_without_witness():
    m = _mR(x="real")
    syms = _make_symbols(m)
    fr = falsify(_parse("(x+1)**2", syms), _parse("x**2+2*x+1", syms), m, syms, n_samples=40)
    assert isinstance(fr, FalsificationReceipt)
    assert fr.passed is True
    assert fr.witness is None
    assert fr.samples_tested > 0
    # honesty: survived != universal proof
    assert "SURVIVED" in fr.coverage_claim and "universal" in fr.coverage_claim


def test_falsify_refutes_false_identity_with_genuine_witness():
    """The witness must be a REAL counterexample: re-evaluating lhs-rhs at it is non-zero."""
    m = _mR(x="real")
    syms = _make_symbols(m)
    fr = falsify(_parse("x**2", syms), _parse("x", syms), m, syms, n_samples=40)
    assert fr.passed is False
    assert fr.witness is not None and "x" in fr.witness
    assert fr.witness_residual is not None
    assert fr.refutation_mode in ("exact", "interval")
    # independent recomputation: the witness genuinely violates the equality
    assert abs(_residual_at_witness("x**2", "x", m, fr.witness)) > 1e-9


def test_falsify_witness_changes_with_the_claim():
    """Driving-input check: two DIFFERENT false claims produce DIFFERENT witnesses/residuals,
    proving the witness is computed from the claim, not a canned constant."""
    m = _mR(x="real")
    syms = _make_symbols(m)
    # x == x+1  -> constant residual -1 everywhere
    fr1 = falsify(_parse("x", syms), _parse("x + 1", syms), m, syms, n_samples=40)
    # x**2 == 2  -> residual depends on x (first anchor x=-3 -> 9-2=7)
    fr2 = falsify(_parse("x**2", syms), _parse("2", syms), m, syms, n_samples=40)
    assert fr1.passed is False and fr2.passed is False
    assert fr1.witness_residual != fr2.witness_residual


# ---------------------------------------------------------------------------
# 3. assess_identity: status + severity are DRIVEN by the inputs (manifest, claim).
# ---------------------------------------------------------------------------

def test_assess_status_flips_with_the_manifest_domain():
    """sqrt(x**2) == x is FALSE on R (x<0 refutes) but TRUE on R+. The ONLY changed input is
    the manifest domain — so a flip proves the manifest is genuinely consumed, not ignored."""
    on_R = assess_identity("sqrtR", "sqrt(x**2)", "x",
                           AssumptionManifest(domain_id="R", variables={"x": "real"}), n_samples=40)
    on_Rp = assess_identity("sqrtRp", "sqrt(x**2)", "x",
                            AssumptionManifest(domain_id="R+", variables={"x": "positive"}), n_samples=40)
    assert on_R.status == "REFUTED"
    assert on_R.falsify.witness["x"] < 0  # the counterexample is a negative x
    assert on_Rp.status == "SURVIVED_NOVEL"
    # REFUTED is non-informative for ranking; severity collapses to 0
    assert on_R.severity == 0.0


def test_assess_severity_penalises_triviality_rewards_information():
    """Severity is a function of the raw difference's informativeness: x==x (0 ops) -> 0,
    an expanded binomial -> > 0. Two different inputs -> two different severities."""
    trivial = assess_identity("triv", "x", "x", _mR(x="real"), n_samples=40)
    informative = assess_identity("info", "(x+1)**2", "x**2 + 2*x + 1", _mR(x="real"), n_samples=40)
    assert trivial.status == "SURVIVED_NOVEL" and informative.status == "SURVIVED_NOVEL"
    assert trivial.severity == 0.0
    assert informative.severity > trivial.severity


def test_assess_proof_tier_reflects_deduction():
    """A deductively proved (grid-survived) identity earns proof_tier 3; the artifact carries
    the actual ProofCertificate, not a placeholder."""
    art = assess_identity("pyth", "sin(x)**2 + cos(x)**2", "1", _mR(x="real"), n_samples=40)
    assert art.status == "SURVIVED_NOVEL"
    assert art.proof_tier == 3
    assert art.proof is not None and art.proof.deductively_proved is True


# ---------------------------------------------------------------------------
# 4. NEVER a false merge: the fingerprint only collapses proved-equal claims.
# ---------------------------------------------------------------------------

def test_fingerprint_merges_only_proved_equal_never_false_merge():
    m = _mR(x="real", y="real")
    syms = _make_symbols(m)
    mh = m.manifest_hash()
    t_comm, fp_comm = fingerprint(_parse("x + y", syms), _parse("y + x", syms), mh)
    t_dbl, fp_dbl = fingerprint(_parse("2*x", syms), _parse("x + x", syms), mh)
    assert t_comm == "proved_equal" and t_dbl == "proved_equal"
    assert fp_comm == fp_dbl  # both collapse to |0 under the same manifest

    # a genuinely different (false) relation must NOT share the proved-equal fingerprint
    t_false, fp_false = fingerprint(_parse("x + y", syms), _parse("x - y", syms), mh)
    assert t_false != "proved_equal"
    assert fp_false != fp_comm


def test_fingerprint_separates_distinct_manifests():
    """The SAME statement under a DIFFERENT manifest must not merge — the manifest_hash is
    a real input to the fingerprint, not decoration."""
    syms = _make_symbols(_mR(x="real"))
    _, fp_real = fingerprint(_parse("x", syms), _parse("x", syms), "manifest-A")
    _, fp_other = fingerprint(_parse("x", syms), _parse("x", syms), "manifest-B")
    assert fp_real != fp_other


# ---------------------------------------------------------------------------
# 5. MANDATORY NEGATIVE / abstention paths (a gate without a test does not exist).
# ---------------------------------------------------------------------------

def test_parse_fails_loud_on_undeclared_symbol():
    """No silent guessing of an undeclared variable's nature — _parse raises ValueError."""
    syms = _make_symbols(_mR(x="real"))
    with pytest.raises(ValueError, match="undeclared free symbols"):
        _parse("x + y", syms)  # y is not in the manifest


def test_assess_inconclusive_on_parse_failure():
    """An undeclared symbol bubbles up to an honest INCONCLUSIVE artifact (never a guessed
    truth value), with severity 0 and no falsification receipt."""
    art = assess_identity("undecl", "x + y", "y + x", _mR(x="real"), n_samples=40)
    assert art.status == "INCONCLUSIVE"
    assert art.severity == 0.0
    assert art.falsify is None
    assert "parse/manifest failure" in art.note


# ---------------------------------------------------------------------------
# 6. PROPERTY-BASED invariants (Hypothesis): the headline must hold for all inputs.
# ---------------------------------------------------------------------------

@given(a=st.integers(min_value=-6, max_value=6), b=st.integers(min_value=-6, max_value=6))
@settings(max_examples=25, deadline=None)
def test_property_true_binomial_identity_always_survives(a, b):
    """For all integer a,b: (x+a)*(x+b) == x^2+(a+b)x+ab is a TRUE identity, so falsify must
    never find a counterexample (the headline deduction/falsification agreement)."""
    m = _mR(x="real")
    syms = _make_symbols(m)
    lhs = _parse(f"(x + {a})*(x + {b})", syms)
    rhs = _parse(f"x**2 + {a + b}*x + {a * b}", syms)
    fr = falsify(lhs, rhs, m, syms, n_samples=30)
    assert fr.passed is True and fr.witness is None


@given(c=st.integers(min_value=1, max_value=9))
@settings(max_examples=15, deadline=None)
def test_property_false_offset_identity_refuted_with_genuine_witness(c):
    """For all c != 0: x^2 == x^2 + c is FALSE, so falsify must REFUTE and the witness must be
    a genuine counterexample (residual ~ -c, definitely non-zero) — never a false survive."""
    m = _mR(x="real")
    syms = _make_symbols(m)
    fr = falsify(_parse("x**2", syms), _parse(f"x**2 + {c}", syms), m, syms, n_samples=30)
    assert fr.passed is False
    assert fr.witness is not None
    residual = _residual_at_witness("x**2", f"x**2 + {c}", m, fr.witness)
    assert math.isclose(residual, -c, rel_tol=1e-9, abs_tol=1e-9)
