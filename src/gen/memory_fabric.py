"""Phase zeta — the shared, conformal-gated memory fabric.

The lower memory layer already exists: ``VerifiedFactsLibrary`` deposits only VERIFIED
claims and returns recalled facts only below a conformal threshold. Zeta is the audit
layer above it: a run-level certificate that says exactly what entered shared memory,
what prior facts were reused, and whether the memory fabric was healthy enough to reuse.

This gate is deliberately deterministic. It does not embed text, query a database, or
call trust-core. It verifies the receipts produced by those layers:

* deposits must point to VERIFIED run claims and preserve source provenance;
* accepted recalls must be calibrated (tau present, score <= tau);
* drift alerts block the certificate;
* lack of baseline is allowed only as honest abstention (no recalls).
"""

from __future__ import annotations

from collections.abc import Iterable

from .core.interfaces import GateFailure, GateResult
from .core.state import (
    ClaimStatus,
    MemoryDeposit,
    MemoryFabricCertificate,
    MemoryHealthStatus,
    MemoryRecallLink,
    RunState,
)


def _claim_sources(claim) -> tuple[str, ...]:
    return tuple(source.url_or_id for source in claim.sources if source.url_or_id.strip())


def build_memory_fabric_certificate(
    state: RunState,
    *,
    recall_results: Iterable[object] = (),
    calibration_ready: bool = False,
    health: MemoryHealthStatus = MemoryHealthStatus.NOT_ENOUGH_BASELINE,
) -> MemoryFabricCertificate:
    """Build a zeta receipt from current run claims and prior recall results.

    ``recall_results`` is intentionally structural: it accepts ``RecallResult`` from
    ``gen.memory`` without making core memory a dependency of this module.
    """
    deposits = [
        MemoryDeposit(claim_id=claim.id, sources=_claim_sources(claim))
        for claim in state.claims
        if claim.status is ClaimStatus.VERIFIED
    ]

    recalls: list[MemoryRecallLink] = []
    for result in recall_results:
        query = str(getattr(result, "query", "")).strip()
        tau = getattr(result, "tau", None)
        for fact in getattr(result, "accepted", ()):
            recalls.append(
                MemoryRecallLink(
                    query=query,
                    claim_id=str(getattr(fact, "claim_id", "")).strip(),
                    score=float(getattr(fact, "score")),
                    tau=tau,
                    sources=tuple(getattr(fact, "sources", ())),
                )
            )

    return MemoryFabricCertificate(
        run_id=state.question.run_id,
        deposits=deposits,
        recalls=recalls,
        calibration_ready=calibration_ready,
        health=health,
        produced_by="memory_fabric",
    )


def _duplicates(values: list[tuple[str, ...]]) -> set[tuple[str, ...]]:
    seen: set[tuple[str, ...]] = set()
    dupes: set[tuple[str, ...]] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def gate_zeta(state: RunState, certificate: MemoryFabricCertificate) -> GateResult:
    """GATE zeta — validate shared-memory deposits and recall links.

    Empty memory fabric is valid abstention. Any accepted reuse, however, must have a
    calibrated conformal threshold and a healthy drift status. Pure; no model/database
    calls.
    """
    failures: list[GateFailure] = []

    if certificate.run_id != state.question.run_id:
        failures.append(
            GateFailure(
                code="MEMORY_RUN_MISMATCH",
                detail=(
                    f"memory certificate belongs to run {certificate.run_id!r}, "
                    f"not {state.question.run_id!r}."
                ),
            )
        )

    if certificate.health is MemoryHealthStatus.DRIFT_ALERT:
        failures.append(
            GateFailure(
                code="MEMORY_DRIFT_ALERT",
                detail="memory fabric reported drift; reuse/deposit requires review.",
            )
        )

    claims_by_id = {claim.id: claim for claim in state.claims}

    for (claim_id,) in sorted(_duplicates([(d.claim_id,) for d in certificate.deposits])):
        failures.append(
            GateFailure(
                code="DUPLICATE_MEMORY_DEPOSIT",
                detail=f"claim {claim_id!r} is deposited more than once.",
                claim_id=claim_id,
            )
        )

    for deposit in certificate.deposits:
        claim = claims_by_id.get(deposit.claim_id)
        if claim is None:
            failures.append(
                GateFailure(
                    code="MEMORY_DEPOSIT_UNKNOWN_CLAIM",
                    detail=f"deposit references unknown claim {deposit.claim_id!r}.",
                    claim_id=deposit.claim_id,
                )
            )
            continue
        if claim.status is not ClaimStatus.VERIFIED:
            failures.append(
                GateFailure(
                    code="MEMORY_DEPOSIT_NOT_VERIFIED",
                    detail=(
                        f"claim {claim.id!r} has status {claim.status.value}; "
                        "only VERIFIED claims may enter shared memory."
                    ),
                    claim_id=claim.id,
                )
            )
        if not claim.sources or not any(source.retrieved for source in claim.sources):
            failures.append(
                GateFailure(
                    code="MEMORY_DEPOSIT_UNSOURCED",
                    detail=f"claim {claim.id!r} has no retrieved source provenance.",
                    claim_id=claim.id,
                )
            )
        claim_source_ids = set(_claim_sources(claim))
        if not set(deposit.sources) <= claim_source_ids:
            failures.append(
                GateFailure(
                    code="MEMORY_DEPOSIT_SOURCE_MISMATCH",
                    detail=(
                        f"deposit for claim {claim.id!r} cites sources "
                        f"{deposit.sources!r}, not a subset of claim sources "
                        f"{tuple(sorted(claim_source_ids))!r}."
                    ),
                    claim_id=claim.id,
                )
            )

    recall_keys = [(recall.query, recall.claim_id) for recall in certificate.recalls]
    for query, claim_id in sorted(_duplicates(recall_keys)):
        failures.append(
            GateFailure(
                code="DUPLICATE_MEMORY_RECALL",
                detail=f"recall {claim_id!r} for query {query!r} appears more than once.",
                claim_id=claim_id,
            )
        )

    if certificate.recalls:
        if not certificate.calibration_ready:
            failures.append(
                GateFailure(
                    code="MEMORY_RECALL_WITHOUT_CALIBRATION",
                    detail="accepted recalls require a ready conformal calibrator.",
                )
            )
        if certificate.health is not MemoryHealthStatus.OK:
            failures.append(
                GateFailure(
                    code="MEMORY_RECALL_WITHOUT_HEALTH_CLEARANCE",
                    detail=(
                        f"accepted recalls require memory health OK; got "
                        f"{certificate.health.value!r}."
                    ),
                )
            )

    for recall in certificate.recalls:
        if recall.tau is None:
            failures.append(
                GateFailure(
                    code="MEMORY_RECALL_WITHOUT_TAU",
                    detail=f"recall {recall.claim_id!r} has no conformal threshold.",
                    claim_id=recall.claim_id,
                )
            )
            continue
        if recall.score > recall.tau:
            failures.append(
                GateFailure(
                    code="MEMORY_RECALL_OUTSIDE_BAND",
                    detail=(
                        f"recall {recall.claim_id!r} score {recall.score:g} exceeds "
                        f"tau {recall.tau:g}."
                    ),
                    claim_id=recall.claim_id,
                )
            )
        if not all(source.strip() for source in recall.sources):
            failures.append(
                GateFailure(
                    code="MEMORY_RECALL_UNSOURCED",
                    detail=f"recall {recall.claim_id!r} does not preserve source ids.",
                    claim_id=recall.claim_id,
                )
            )

    return GateResult(gate="zeta", passed=not failures, failures=failures)


__all__ = ["build_memory_fabric_certificate", "gate_zeta"]
