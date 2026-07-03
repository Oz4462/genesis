"""Tests für den deduktiven CAS-Proof-Tier (math-research, Stein c).

CAS-certified ist NICHT Lean-Kernel-verifiziert: sympy simplify ist heuristisch, daher
nur im sicheren Fragment (keine Integral/Sum/undef-Funktion/Float), rational, kein force,
und nur wenn das Gitter ebenfalls überlebte (Defence-in-Depth). Grid-Refutation überschreibt
CAS immer.
"""

import sympy as sp

from gen.identity_research import (
    AssumptionManifest,
    assess_identity,
    prove_identity,
)


def _mR():
    return AssumptionManifest(domain_id="R", variables={"x": "real"})


def test_prove_identity_cas_certifies_true_identity():
    x = sp.Symbol("x", real=True)
    cert = prove_identity(sp.sin(x)**2 + sp.cos(x)**2, sp.Integer(1), grid_passed=True, lean_statement="L")
    assert cert.method == "cas_simplify"
    assert cert.deductively_proved is True
    assert cert.lean_status == "cas_certified"
    assert "lean kernel" in cert.notes.lower()   # honest: CAS, not kernel-verified


def test_grid_refutation_overrides_cas():
    x = sp.Symbol("x", real=True)
    cert = prove_identity(x, x + 1, grid_passed=False, lean_statement="L")
    assert cert.method == "none"
    assert cert.deductively_proved is False
    assert cert.lean_status == "admitted"


def test_outside_safe_fragment_is_grid_only_not_proved():
    x = sp.Symbol("x", real=True)
    g = sp.Function("g")
    # undefined function: sympy cannot deductively reduce -> outside safe CAS fragment
    cert = prove_identity(g(x), g(2 * x), grid_passed=True, lean_statement="L")
    assert cert.method == "grid_only"
    assert cert.deductively_proved is False
    assert cert.lean_status == "admitted"


def test_assess_attaches_cas_certified_proof_tier_3():
    art = assess_identity("pyth", "sin(x)**2 + cos(x)**2", "1", _mR())
    assert art.status == "SURVIVED_NOVEL"
    assert art.proof is not None
    assert art.proof.deductively_proved is True
    assert art.proof.lean_status == "cas_certified"
    assert art.proof_tier == 3
    assert art.lean_statement.strip().endswith(":= by admit")   # statement recorded, not kernel-run


def test_refuted_identity_has_no_proof_cert():
    art = assess_identity("false1", "x", "x + 1", _mR())
    assert art.status == "REFUTED"
    assert art.proof is None
