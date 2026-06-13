"""Opt-in live wiring: run the GENESIS pipeline, deposit verified facts, sign an audit.

This composes the optional integrations (Phase 2 memory + Phase 4 audit) AROUND the
core pipeline without touching it: GENESIS core stays numpy-only, and only callers
that import `gen.integration` pull the `verify` extra. The run's claims are read back
from the ledger by run_id — no change to runner/agents is needed.

After a run:
  * every VERIFIED claim is deposited into the cross-run `VerifiedFactsLibrary` (so the
    next run can reuse it — closing gap #1 end to end), and
  * a tamper-evident `RunAuditRecord` is signed over the ledger digest + model ids.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..audit import AuditEnvelope, RunAuditRecord, audit_from_claims, sign_audit
from ..config import Config, config_hash, default_config
from ..core.state import Claim, Report
from ..memory import RecalledFact, VerifiedFactsLibrary
from ..runner import Dependencies, make_run_id, run


@dataclass(frozen=True)
class AuditedRunResult:
    """What an audited run produced, for the operator's records."""

    run_id: str
    report: Report
    claims: Sequence[Claim]
    n_remembered: int
    audit: AuditEnvelope | None
    audit_record: RunAuditRecord | None
    reused_facts: tuple[RecalledFact, ...] = ()


async def audited_run(
    question_text: str,
    deps: Dependencies,
    *,
    created_at: str,
    config: Config | None = None,
    run_id: str | None = None,
    library: VerifiedFactsLibrary | None = None,
    recall: bool = False,
    keystore=None,
    audit_key_id: str | None = None,
) -> AuditedRunResult:
    """Run Phase α, then deposit verified facts and sign an audit (both optional).

    Args:
        created_at: ISO timestamp recorded in the audit (caller-supplied so the
            record stays reproducible — code never reads the clock).
        library: if given, VERIFIED claims are deposited for cross-run reuse.
        recall: if True (and library given), the question is recalled against the
            library FIRST; prior verified facts within the conformal band are returned
            as ``reused_facts`` (each carrying its original provenance). This is the
            cross-run prefilter — a provenance-preserving signal of what need not be
            re-researched. It does not yet short-circuit the run itself (that would
            collide with the per-run fetch-audit invariant; deferred).
        keystore / audit_key_id: if both given, a signed audit envelope is produced.
    """
    config = config or default_config()
    chash = config_hash(config)
    rid = run_id or make_run_id(question_text, chash)

    reused: tuple[RecalledFact, ...] = ()
    if recall and library is not None:
        reused = library.recall(question_text).accepted

    report = await run(question_text, deps, config=config, run_id=rid)
    claims = await deps.ledger.get_claims(rid)

    n_remembered = library.remember(claims) if library is not None else 0

    audit_env: AuditEnvelope | None = None
    record: RunAuditRecord | None = None
    if keystore is not None and audit_key_id is not None:
        record = audit_from_claims(
            run_id=rid,
            generator_model=deps.generator_llm.model,
            verifier_model=deps.verifier_llm.model,
            claims=claims,
            config_hash=chash,
            created_at=created_at,
        )
        audit_env = sign_audit(record, keystore, audit_key_id)

    return AuditedRunResult(
        run_id=rid,
        report=report,
        claims=claims,
        n_remembered=n_remembered,
        audit=audit_env,
        audit_record=record,
        reused_facts=reused,
    )


__all__ = ["AuditedRunResult", "audited_run"]
