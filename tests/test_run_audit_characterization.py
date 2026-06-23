"""Characterization + facade audit for ``gen.audit.run_audit``.

Pins the documented guarantees of the signed, tamper-evident run audit so a
regression in any of them fails loudly:

  * ``digest_claims`` is a deterministic, source-order-independent function of
    the claims, yet sensitive to a claim's id / status / text (so the digest is
    a real fingerprint of *what* was claimed, not a constant).
  * ``audit_from_claims`` computes the correct status counts + ``n_claims`` and
    its ``ledger_digest`` equals ``digest_claims(claims)`` (the input is genuinely
    consumed — no canned record).
  * ``sign_audit`` -> ``verify_audit`` round-trips to an equal ``RunAuditRecord``.
  * Tampering with the envelope payload (flip a status count) -> ``BadSignatureError``.
  * A DIFFERENT key fails verification -> ``BadSignatureError``.
  * An unknown key id -> ``KeyError``; a wrong ``payload_type`` -> ``ValueError``.

``run_audit`` hard-imports trust-core (the optional ``verify`` extra) at module
load, so the crypto tests require that extra. Rather than a module-level
``importorskip`` — which collects ZERO tests and makes pytest exit 5 ("no tests
collected") when the extra is absent — the trust-core tests carry a ``skipif``
mark, and ``test_import_contract`` ALWAYS runs: it pins the module's documented
behaviour in BOTH environments (a clean ``ImportError`` without the extra, a real
import with it). So the file always collects at least one passing test and the
full pytest gate stays green either way.

Conclusion (see docs/audit/DEPTH_AUDIT_run_audit.md): REAL. No source edit needed.
"""

from __future__ import annotations

import base64
import importlib
import importlib.util
import json

import pytest

# Detect the optional `verify` extra once. We must NOT import run_audit (or its
# gen.* siblings) at module top unconditionally: run_audit raises ImportError
# without trust-core, which would turn collection into an ERROR rather than a
# clean skip. Using a skipif mark (instead of a module-level importorskip) keeps
# the trust-core tests COLLECTED-then-skipped, so the file never yields pytest
# exit 5 ("no tests collected") when the extra is absent.
HAS_TRUST_CORE = importlib.util.find_spec("trust_core") is not None
requires_trust_core = pytest.mark.skipif(
    not HAS_TRUST_CORE,
    reason="trust-core ('verify' extra) not installed",
)

if HAS_TRUST_CORE:
    from nacl.exceptions import BadSignatureError
    from trust_core.receipts.keystore import KeyStore

    from gen.audit import (
        AuditEnvelope,
        RunAuditRecord,
        audit_from_claims,
        digest_claims,
        sign_audit,
        verify_audit,
    )
    from gen.audit.run_audit import _PAYLOAD_TYPE
    from gen.core.state import Claim, ClaimStatus, SourceRef


# --- builders (only invoked by trust-core tests) ----------------------------

def _src(uid: str) -> SourceRef:
    return SourceRef(url_or_id=uid, retrieved=True)


def _claim(cid: str, status: ClaimStatus, *, text: str | None = None,
           sources: list[SourceRef] | None = None) -> Claim:
    return Claim(
        id=cid,
        text=text if text is not None else f"claim {cid}",
        sources=sources if sources is not None else [_src(f"src://{cid}")],
        status=status,
    )


def _claims() -> list[Claim]:
    # Mix of every ClaimStatus; one claim carries multiple sources so the
    # source-order-independence guarantee is actually exercised.
    return [
        _claim("c0", ClaimStatus.VERIFIED),
        _claim("c1", ClaimStatus.VERIFIED,
               sources=[_src("src://b"), _src("src://a"), _src("src://c")]),
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


def _keyed_store():
    ks = KeyStore()
    key_id = ks.generate(scope="genesis-audit").key_id
    return ks, key_id


# --- always-on: documented import contract (keeps collection non-empty) -----

def test_import_contract():
    """The module's documented load behaviour, asserted in BOTH environments.

    Without the `verify` extra it must raise a helpful ImportError (no silent
    partial import); with it, the public verifier surface must be importable.
    This test always collects+runs, so the file never yields pytest exit 5.
    """
    if HAS_TRUST_CORE:
        mod = importlib.import_module("gen.audit.run_audit")
        assert hasattr(mod, "verify_audit") and hasattr(mod, "sign_audit")
    else:
        with pytest.raises(ImportError) as exc:
            importlib.import_module("gen.audit.run_audit")
        # When `gen` itself is importable, the failure MUST be the module's
        # documented trust-core guard (a clean, helpful ImportError) — not some
        # unrelated import error.
        if importlib.util.find_spec("gen") is not None:
            assert "trust-core is required" in str(exc.value)


# --- digest_claims: deterministic, order-independent, content-sensitive -----

@requires_trust_core
def test_digest_is_deterministic():
    assert digest_claims(_claims()) == digest_claims(_claims())
    # A digest is a 64-char SHA-256 hex string, not an empty/canned value.
    d = digest_claims(_claims())
    assert len(d) == 64 and all(ch in "0123456789abcdef" for ch in d)


@requires_trust_core
def test_digest_independent_of_source_order_within_a_claim():
    forward = [_claim("x", ClaimStatus.VERIFIED,
                      sources=[_src("u://1"), _src("u://2"), _src("u://3")])]
    reverse = [_claim("x", ClaimStatus.VERIFIED,
                      sources=[_src("u://3"), _src("u://2"), _src("u://1")])]
    assert digest_claims(forward) == digest_claims(reverse)


@requires_trust_core
def test_digest_sensitive_to_claim_text():
    base = [_claim("c", ClaimStatus.VERIFIED, text="alpha")]
    other = [_claim("c", ClaimStatus.VERIFIED, text="beta")]
    assert digest_claims(base) != digest_claims(other)


@requires_trust_core
def test_digest_sensitive_to_status():
    base = [_claim("c", ClaimStatus.VERIFIED)]
    other = [_claim("c", ClaimStatus.REFUTED)]
    assert digest_claims(base) != digest_claims(other)


@requires_trust_core
def test_digest_sensitive_to_id():
    base = [_claim("c0", ClaimStatus.VERIFIED, text="same", sources=[_src("u://1")])]
    other = [_claim("c1", ClaimStatus.VERIFIED, text="same", sources=[_src("u://1")])]
    assert digest_claims(base) != digest_claims(other)


@requires_trust_core
def test_digest_sensitive_to_claim_order():
    # Claim order is part of the canonical record (ledger insertion order, A5),
    # so reordering the claims is a real change in what the run produced.
    a = _claims()
    b = list(reversed(a))
    assert digest_claims(a) != digest_claims(b)


# --- audit_from_claims: real counts + digest wiring -------------------------

@requires_trust_core
def test_counts_and_n_claims():
    r = _record()
    assert r.n_claims == 5
    assert r.n_verified == 2
    assert r.n_refuted == 1
    assert r.n_unsupported == 1
    assert r.n_unverified == 1
    # Counts cover every claim — the audit hides nothing.
    assert r.n_verified + r.n_refuted + r.n_unsupported + r.n_unverified == r.n_claims


@requires_trust_core
def test_ledger_digest_equals_digest_claims():
    claims = _claims()
    r = audit_from_claims(
        run_id="run-2",
        generator_model="g",
        verifier_model="v",
        claims=claims,
        config_hash="cfg",
        created_at="2026-06-13T00:00:00+00:00",
    )
    assert r.ledger_digest == digest_claims(claims)


@requires_trust_core
def test_record_reflects_inputs():
    r = _record()
    assert r.run_id == "run-1"
    assert r.generator_model == "qwen3.5:9b"
    assert r.verifier_model == "gemma4:12b"
    assert r.config_hash == "cfg-abc"
    assert r.created_at == "2026-06-13T00:00:00+00:00"


# --- sign -> verify round-trip ----------------------------------------------

@requires_trust_core
def test_sign_verify_roundtrip_returns_equal_record():
    ks, key_id = _keyed_store()
    rec = _record()
    env = sign_audit(rec, ks, key_id)
    assert env.payload_type == _PAYLOAD_TYPE
    assert env.key_id == key_id
    back = verify_audit(env, ks)
    assert back == rec
    assert isinstance(back, RunAuditRecord)


# --- tamper-evidence --------------------------------------------------------

@requires_trust_core
def test_tampering_with_a_status_count_is_detected():
    ks, key_id = _keyed_store()
    env = sign_audit(_record(), ks, key_id)

    # Decode the signed payload, flip a status count, re-encode -> the payload
    # no longer matches the signature, so verification must fail loudly.
    payload = json.loads(base64.b64decode(env.payload_b64).decode("utf-8"))
    assert payload["n_verified"] == 2
    payload["n_verified"] = 99
    forged_b64 = base64.b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    tampered = AuditEnvelope(
        payload_type=env.payload_type,
        payload_b64=forged_b64,
        key_id=env.key_id,
        sig_b64=env.sig_b64,
    )
    with pytest.raises(BadSignatureError):
        verify_audit(tampered, ks)


@requires_trust_core
def test_signature_tamper_is_detected():
    ks, key_id = _keyed_store()
    env = sign_audit(_record(), ks, key_id)
    raw = bytearray(base64.b64decode(env.sig_b64))
    raw[0] ^= 0x01  # corrupt the signature itself
    forged = AuditEnvelope(
        payload_type=env.payload_type,
        payload_b64=env.payload_b64,
        key_id=env.key_id,
        sig_b64=base64.b64encode(bytes(raw)).decode("ascii"),
    )
    with pytest.raises(BadSignatureError):
        verify_audit(forged, ks)


# --- wrong / unknown key + bad payload type ---------------------------------

@requires_trust_core
def test_different_key_fails_verification():
    # Same keystore holds two keys; verify against the OTHER key id. The key id
    # is known (no KeyError) but its verify key does not match the signature ->
    # BadSignatureError, proving the signature is really bound to its signing key.
    ks = KeyStore()
    signing_key = ks.generate(scope="genesis-audit").key_id
    other_key = ks.generate(scope="genesis-audit").key_id
    assert other_key != signing_key
    env = sign_audit(_record(), ks, signing_key)
    rebound = AuditEnvelope(
        payload_type=env.payload_type,
        payload_b64=env.payload_b64,
        key_id=other_key,
        sig_b64=env.sig_b64,
    )
    with pytest.raises(BadSignatureError):
        verify_audit(rebound, ks)


@requires_trust_core
def test_unknown_key_id_raises_keyerror():
    ks_signer, key_id = _keyed_store()
    env = sign_audit(_record(), ks_signer, key_id)
    empty_store = KeyStore()  # never saw `key_id`
    with pytest.raises(KeyError):
        verify_audit(env, empty_store)


@requires_trust_core
def test_wrong_payload_type_raises_valueerror():
    ks, key_id = _keyed_store()
    env = sign_audit(_record(), ks, key_id)
    bad = AuditEnvelope(
        payload_type="application/json",  # not the run-audit media type
        payload_b64=env.payload_b64,
        key_id=env.key_id,
        sig_b64=env.sig_b64,
    )
    with pytest.raises(ValueError):
        verify_audit(bad, ks)


# --- property-based: source-order invariance of the digest ------------------

if HAS_TRUST_CORE:
    from hypothesis import given
    from hypothesis import strategies as st

    @given(urls=st.lists(st.text(min_size=1, max_size=12), min_size=1, max_size=6, unique=True))
    def test_digest_invariant_under_source_permutation(urls):
        """For any set of source ids, permuting them within a claim leaves the
        digest unchanged — the digest sorts sources, so order carries no
        information (A5)."""
        forward = [Claim(id="p", text="t", sources=[_src(u) for u in urls],
                         status=ClaimStatus.VERIFIED)]
        reverse = [Claim(id="p", text="t", sources=[_src(u) for u in reversed(urls)],
                         status=ClaimStatus.VERIFIED)]
        assert digest_claims(forward) == digest_claims(reverse)
