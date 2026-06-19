"""Math certification loop (discovery/proof_loop.py): propose -> mpmath prefilter -> z3 kernel.

Pins the honest label discipline (Entdecken != Zertifizieren): a true polynomial identity is kernel-closed
("Satz"); a numerically false one is refuted by the high-precision prefilter; a domain-hole identity that
SymPy would wrongly cancel is refuted by the z3 kernel with a counterexample; a TRUE transcendental identity
z3 cannot model is only "Kandidat", never "Satz". Offline, deterministic (z3 + sympy + mpmath).
"""

from gen.discovery.proof_loop import IdentityClaim, prove_identity


def test_true_polynomial_identity_is_certified_as_satz():
    v = prove_identity(IdentityClaim("(x+1)**2", "x**2 + 2*x + 1", {"x": "real"}, "R"))
    assert v.status == "Satz"
    assert v.kernel == "z3_qfnra" and v.numeric_ok


def test_numerically_false_identity_is_refuted_by_the_prefilter():
    v = prove_identity(IdentityClaim("sin(x)", "x", {"x": "real"}, "R"))
    assert v.status == "widerlegt"
    assert not v.numeric_ok and v.kernel == "mpmath"        # caught at high precision before any solver


def test_domain_hole_identity_is_refuted_by_the_kernel_with_a_counterexample():
    # SymPy would cancel (x^2+x)/x to x+1 and call it true; the z3 kernel finds the x=0 hole.
    v = prove_identity(IdentityClaim("(x**2 + x)/x", "x + 1", {"x": "real"}, "R"))
    assert v.status == "widerlegt"
    assert v.kernel == "z3_qfnra"
    assert v.counterexample is not None and v.counterexample.get("x") == "0"


def test_true_transcendental_identity_is_candidate_not_satz():
    # sin^2 + cos^2 = 1 is TRUE and agrees numerically, but z3 cannot model sin/cos -> only "Kandidat".
    v = prove_identity(IdentityClaim("sin(x)**2 + cos(x)**2", "1", {"x": "real"}, "R"))
    assert v.status == "Kandidat"                            # honest: discovered/agrees, but NOT certified
    assert v.numeric_ok


def test_unparseable_claim_is_unsupported():
    v = prove_identity(IdentityClaim("x +* 1", "x", {"x": "real"}, "R"))
    assert v.status == "unsupported"


def test_certification_is_deterministic():
    a = prove_identity(IdentityClaim("(x+1)**2", "x**2 + 2*x + 1", {"x": "real"}, "R"))
    b = prove_identity(IdentityClaim("(x+1)**2", "x**2 + 2*x + 1", {"x": "real"}, "R"))
    assert (a.status, a.kernel) == (b.status, b.kernel)
