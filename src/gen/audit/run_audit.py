"""Tamper-evident, independently verifiable run audit (Phase 4 / governance).

NET-NEW for GENESIS: turn a run's ledger into a signed audit record so an operator
(or a regulator, EU-AI-Act-style) can prove what the run claimed, with which models,
and that the record was not altered. PoV-4 proved sign->verify->tamper->wrong-key.

Built on trust-core's Ed25519 `KeyStore` (generic signer + key rotation/revocation) —
the same primitive VERIDEX uses — via the optional `verify` extra. VERIDEX's full
Annex-IV / Article-12 web service is a DEPLOYMENT surface (FastAPI/k8s) and is out of
scope here; GENESIS stays a local library. The drift half of governance is
`gen.verification.drift_monitor` (Phase 1).

Honesty/determinism: the audit digest is a canonical, reproducible function of the
claims (A5); signing uses DSSE Pre-Authentication Encoding so canonicalization attacks
on the JSON are rejected; verification fails loudly on any tampering.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from ..core.state import Claim, ClaimStatus

try:
    from trust_core.receipts.keystore import KeyStore
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "trust-core is required for gen.audit. Install the optional extra: "
        "pip install -e '.[verify]'."
    ) from exc

_PAYLOAD_TYPE = "application/vnd.genesis.run-audit+json"


def _pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (in-toto), binary-safe + length-prefixed."""
    t = payload_type.encode("utf-8")
    return (
        b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" "
        + str(len(payload)).encode() + b" " + payload
    )


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def digest_claims(claims: Sequence[Claim]) -> str:
    """Reproducible SHA-256 over a canonical claim summary (id|status|text|sources).

    Order-independent in sources (sorted), order-preserving in claims (ledger
    insertion order is itself deterministic, see InMemoryLedgerStore). Two runs that
    produce the same claims yield the same digest — the anchor of an honest audit.
    """
    h = hashlib.sha256()
    for c in claims:
        src = "|".join(sorted(s.url_or_id for s in c.sources))
        h.update(f"{c.id}\x1f{c.status.value}\x1f{c.text}\x1f{src}\x1e".encode())
    return h.hexdigest()


@dataclass(frozen=True)
class RunAuditRecord:
    """What a run claimed, with which models — the signed payload."""

    run_id: str
    generator_model: str
    verifier_model: str
    n_claims: int
    n_verified: int
    n_refuted: int
    n_unsupported: int
    n_unverified: int
    ledger_digest: str
    config_hash: str
    created_at: str  # caller-supplied ISO string (kept out of code for determinism)

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class AuditEnvelope:
    """DSSE-shaped signed envelope around a RunAuditRecord payload."""

    payload_type: str
    payload_b64: str
    key_id: str
    sig_b64: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "payloadType": self.payload_type,
                "payload": self.payload_b64,
                "keyid": self.key_id,
                "sig": self.sig_b64,
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def audit_from_claims(
    *,
    run_id: str,
    generator_model: str,
    verifier_model: str,
    claims: Sequence[Claim],
    config_hash: str,
    created_at: str,
) -> RunAuditRecord:
    """Build a RunAuditRecord from a run's ledger claims (status counts + digest)."""
    counts = {s: 0 for s in ClaimStatus}
    for c in claims:
        counts[c.status] += 1
    return RunAuditRecord(
        run_id=run_id,
        generator_model=generator_model,
        verifier_model=verifier_model,
        n_claims=len(claims),
        n_verified=counts[ClaimStatus.VERIFIED],
        n_refuted=counts[ClaimStatus.REFUTED],
        n_unsupported=counts[ClaimStatus.UNSUPPORTED],
        n_unverified=counts[ClaimStatus.UNVERIFIED],
        ledger_digest=digest_claims(claims),
        config_hash=config_hash,
        created_at=created_at,
    )


def sign_audit(record: RunAuditRecord, keystore: KeyStore, key_id: str) -> AuditEnvelope:
    """Sign a run-audit record into a DSSE envelope with a trust-core key."""
    payload = record.canonical_bytes()
    sig = keystore.sign(key_id, _pae(_PAYLOAD_TYPE, payload))
    return AuditEnvelope(
        payload_type=_PAYLOAD_TYPE,
        payload_b64=_b64(payload),
        key_id=key_id,
        sig_b64=_b64(sig),
    )


def verify_audit(envelope: AuditEnvelope, keystore: KeyStore) -> RunAuditRecord:
    """Verify an audit envelope and return its record, or raise on tamper/bad key.

    Raises:
        ValueError: unexpected payload type.
        nacl.exceptions.BadSignatureError: signature does not match the payload
            (tampering) or the key does not match.
        KeyError: the envelope's key id is unknown to the keystore.
    """
    if envelope.payload_type != _PAYLOAD_TYPE:
        raise ValueError(f"unexpected payloadType {envelope.payload_type!r}")
    payload = _b64d(envelope.payload_b64)
    vk = keystore.verify_key_of(envelope.key_id)
    vk.verify(_pae(envelope.payload_type, payload), _b64d(envelope.sig_b64))  # raises on mismatch
    data = json.loads(payload.decode("utf-8"))
    return RunAuditRecord(**data)


__all__ = [
    "RunAuditRecord",
    "AuditEnvelope",
    "audit_from_claims",
    "sign_audit",
    "verify_audit",
    "digest_claims",
]
