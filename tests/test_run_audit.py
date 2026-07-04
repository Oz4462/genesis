"""Tests for the signed run audit (Phase 4 / governance).

Skips without trust-core. Proves PoV-4 as a production module: build->sign->verify
roundtrips, tampering is detected, an unknown key is rejected, and the digest is a
deterministic function of the claims.
"""

from __future__ import annotations

import base64

import pytest

# Dotted on purpose: the PyPI 'trust-core' namesake ships no `receipts` — a bare
# importorskip("trust_core") would pass there and turn collection into an ERROR.
pytest.importorskip("trust_core.receipts.keystore")

from nacl.exceptions import BadSignatureError  # noqa: E402

from gen.audit import (  # noqa: E402
    AuditEnvelope,
    audit_from_claims,
    digest_claims,
    sign_audit,
    verify_audit,
)
from gen.core.state import Claim, ClaimStatus, SourceRef  # noqa: E402
from trust_core.receipts.keystore import KeyStore  # noqa: E402


def _claim(cid: str, status: ClaimStatus) -> Claim:
    return Claim(
        id=cid,
        text=f"claim {cid}",
        sources=[SourceRef(url_or_id=f"src://{cid}", retrieved=True)],
        status=status,
    )


def _claims():
    return [
        _claim("c0", ClaimStatus.VERIFIED),
        _claim("c1", ClaimStatus.VERIFIED),
        _claim("c2", ClaimStatus.REFUTED),
        _claim("c3", ClaimStatus.UNSUPPORTED),
        _claim("c4", ClaimStatus.UNVERIFIED),
    ]


def _record():
    return audit_from_claims(
        run_id="run-1",
        generator_model="qwen3.5:9b",
        verifier_model="gemma4:12b",
        claims=_claims(),
        config_hash="cfg-abc",
        created_at="2026-06-13T00:00:00+00:00",
    )


def test_counts_and_deterministic_digest():
    r = _record()
    assert (r.n_claims, r.n_verified, r.n_refuted, r.n_unsupported, r.n_unverified) == (5, 2, 1, 1, 1)
    assert digest_claims(_claims()) == digest_claims(_claims())  # deterministic


def test_sign_verify_roundtrip():
    ks = KeyStore()
    key = ks.generate(scope="genesis-audit").key_id
    rec = _record()
    env = sign_audit(rec, ks, key)
    back = verify_audit(env, ks)
    assert back == rec


def test_tamper_is_detected():
    ks = KeyStore()
    key = ks.generate(scope="genesis-audit").key_id
    env = sign_audit(_record(), ks, key)
    raw = bytearray(base64.b64decode(env.payload_b64))
    raw[len(raw) // 2] ^= 0x01
    tampered = AuditEnvelope(
        payload_type=env.payload_type,
        payload_b64=base64.b64encode(bytes(raw)).decode("ascii"),
        key_id=env.key_id,
        sig_b64=env.sig_b64,
    )
    with pytest.raises(BadSignatureError):
        verify_audit(tampered, ks)


def test_unknown_key_rejected():
    ks_signer = KeyStore()
    key = ks_signer.generate(scope="genesis-audit").key_id
    env = sign_audit(_record(), ks_signer, key)
    other_store = KeyStore()  # does not know `key`
    with pytest.raises(KeyError):
        verify_audit(env, other_store)
