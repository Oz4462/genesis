"""GENESIS run-audit (governance): tamper-evident, independently verifiable audit
records signed with trust-core Ed25519 keys. Optional `verify` extra. See run_audit.py."""

from __future__ import annotations

from .run_audit import (
    AuditEnvelope,
    RunAuditRecord,
    audit_from_claims,
    digest_claims,
    sign_audit,
    verify_audit,
)

__all__ = [
    "RunAuditRecord",
    "AuditEnvelope",
    "audit_from_claims",
    "sign_audit",
    "verify_audit",
    "digest_claims",
]
