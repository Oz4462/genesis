"""Security validators — birthday bound, SP 800-57 strengths, GCM budget.

Exact anchors: p(n=10 bits, q=4) = 16/2048 = 0.0078125 by hand; q=2^32 draws
from a 96-bit space give p = 2^-33 (exactly half the NIST 2^-32 bound, SF=2)
while q=2^33 exceeds it; the SP 800-57 equivalence row AES-128 ≡ RSA-3072 ≡
ECC-P-256 comes out as the SAME 128-bit strength; RSA-2048 honestly fails the
128-bit default but passes a declared 112-bit requirement; the GCM budget is
inclusive at exactly 2^32 and fails one beyond. Unknown mechanisms raise —
never a guessed strength.

Offline, no LLM, no numpy.

Run:  pytest tests/test_security.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.security import (  # noqa: E402
    GCM_IV_COLLISION_BOUND,
    birthday_bound_check,
    birthday_collision_probability,
    gcm_invocation_budget_check,
    key_security_check,
    security_strength_bits,
)


# ------------------------------------------------------------- birthday bound
def test_birthday_probability_by_hand():
    assert birthday_collision_probability(10.0, 4.0) == pytest.approx(16.0 / 2048.0)


def test_gcm_style_nonce_budget_passes_and_fails_around_the_nist_bound():
    ok = birthday_bound_check(96.0, float(2 ** 32))      # p = 2^-33 = bound/2
    assert ok["ok"] and ok["safety_factor"] == pytest.approx(2.0)
    assert ok["max_collision_prob"] == GCM_IV_COLLISION_BOUND
    bad = birthday_bound_check(96.0, float(2 ** 33))     # p = 2^-31 = 2x bound
    assert not bad["ok"] and bad["safety_factor"] == pytest.approx(0.5)


def test_birthday_probability_clamps_and_rejects_nonsense():
    assert birthday_collision_probability(4.0, 100.0) == 1.0   # approximation capped
    with pytest.raises(ValueError):
        birthday_collision_probability(0.0, 5.0)
    with pytest.raises(ValueError):
        birthday_bound_check(96.0, 10.0, max_collision_prob=0.0)


# ---------------------------------------------------------- SP 800-57 strength
def test_the_128_bit_equivalence_row():
    # AES-128 = RSA-3072 = ECC-P-256: the SP 800-57 Table-2 row, encoded exactly
    s_sym = security_strength_bits("symmetric", 128.0)
    s_rsa = security_strength_bits("rsa", 3072.0)
    s_ecc = security_strength_bits("ecc", 256.0)
    assert s_sym == s_rsa == s_ecc == 128.0


def test_rsa_2048_is_112_bits_honest_about_the_default():
    weak = key_security_check("rsa", 2048.0)             # default requires 128
    assert not weak["ok"] and weak["strength_bits"] == 112.0
    legacy = key_security_check("rsa", 2048.0, required_bits=112.0)
    assert legacy["ok"] and legacy["safety_factor"] == pytest.approx(1.0)


def test_table_rows_and_below_table_modulus():
    assert security_strength_bits("rsa", 7680.0) == 192.0
    assert security_strength_bits("rsa", 15360.0) == 256.0
    assert security_strength_bits("rsa", 1024.0) == 80.0
    assert security_strength_bits("rsa", 512.0) == 0.0   # below every row
    assert not key_security_check("rsa", 512.0)["ok"]


def test_unknown_mechanism_raises_never_guesses():
    with pytest.raises(ValueError):
        security_strength_bits("kyber", 1024.0)
    with pytest.raises(ValueError):
        key_security_check("symmetric", 0.0)
    with pytest.raises(ValueError):
        key_security_check("symmetric", 128.0, required_bits=0.0)


# ------------------------------------------------------------------ GCM budget
def test_gcm_budget_inclusive_at_the_standard_limit():
    at = gcm_invocation_budget_check(float(2 ** 32))
    assert at["ok"] and at["safety_factor"] == pytest.approx(1.0)
    over = gcm_invocation_budget_check(float(2 ** 32) + 1.0)
    assert not over["ok"]
    assert gcm_invocation_budget_check(0.0)["safety_factor"] == float("inf")
    with pytest.raises(ValueError):
        gcm_invocation_budget_check(-1.0)


# ------------------------------------------------------------ gate auto-select
def test_crypto_quantities_select_and_gate_honestly():
    from gen.core.state import Quantity, Specification, ValueOrigin
    from gen.physics_selection import evaluate_spec_physics

    def q(qid, v, m):
        return Quantity(id=qid, name=qid, value=v, unit="1",
                        origin=ValueOrigin.DECISION, rationale="x", measurand=m)

    good = Specification(run_id="c1", idea="messenger crypto sizing", quantities=[
        q("nb", 96.0, "crypto.nonce_bits"),
        q("mpk", float(2 ** 32), "crypto.messages_per_key"),
        q("ecc", 256.0, "crypto.ecc_key_bits"),
        q("gcm", float(2 ** 30), "crypto.gcm_invocations"),
    ])
    r = evaluate_spec_physics(good)
    assert r["gate"].passed and len(r["checks"]) == 3 and r["gaps"] == []

    weak = Specification(run_id="c2", idea="legacy RSA", quantities=[
        q("rsa", 2048.0, "crypto.rsa_modulus_bits"),
    ])
    r2 = evaluate_spec_physics(weak)
    assert not r2["gate"].passed                          # 112 < 128: definite finding
    assert r2["gate"].failures[0].code == "PHYSICS_CHECK_FAILED"