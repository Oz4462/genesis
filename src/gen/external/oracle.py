"""oracle — the third plugin type: an EXTERNAL ORACLE whose answer is a GATED claim, never raw truth.

INVENTOR §10¾ D. A foundation model, a heavy simulator, or a domain database can answer a question GENESIS
cannot answer in-house (a protein structure, a weather field, a materials property). The anti-hallucination
invariant still holds: an oracle's output is a PROPOSAL with provenance and uncertainty — exactly like an LLM
proposal — and a deterministic gate decides. It is NEVER a bare fact written straight into the ledger.

Two structural guarantees make "ungated raw oracle output" impossible:
  1. Every :class:`OracleClaim` REQUIRES a validated :class:`ExternalBinding` (TC1) — so it always carries a
     license + provenance, and a non-commercial/unknown-licensed oracle could not even be constructed.
  2. The ONLY path into the ledger (:func:`record_oracle_claim`) writes status **UNVERIFIED** — an oracle can
     never stamp a VERIFIED fact. Promotion to VERIFIED is a separate deterministic gate's job, not the
     oracle's. (Contrast TC1's ``record_binding``, which records the LICENSE — a checkable property — as
     VERIFIED; the oracle's ANSWER is unverified.)

Offline, deterministic given an oracle response; the live oracle call is the oracle's own concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, runtime_checkable

from ..core.state import Claim, ClaimStatus, SourceRef, SourceSupport
from .registry import ExternalBinding


@dataclass(frozen=True)
class OracleClaim:
    """An external oracle's answer as a gated PROPOSAL (never raw truth).

    ``subject`` is what was asked; ``statement`` is the human-readable answer; ``value``/``uncertainty`` are
    the optional numeric answer and its honest uncertainty (None when the oracle reports none — which itself
    is recorded, not hidden); ``binding`` is the validated external source (license + provenance, TC1);
    ``oracle_provenance`` is the specific call (query + model version). An ``OracleClaim`` cannot exist without
    a validated binding, so it always carries a license."""

    subject: str
    statement: str
    binding: ExternalBinding
    oracle_provenance: str
    value: Optional[float] = None
    uncertainty: Optional[float] = None
    confidence: float = 0.5

    def __post_init__(self) -> None:
        if not (self.subject and self.statement and self.oracle_provenance):
            raise ValueError("OracleClaim needs a non-empty subject, statement, and oracle_provenance")
        if not isinstance(self.binding, ExternalBinding):
            raise TypeError("OracleClaim requires a validated ExternalBinding (license + provenance)")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")


@runtime_checkable
class ExternalOracle(Protocol):
    """The external-oracle plugin contract. ``binding`` ties the oracle to a validated, licensed source;
    ``query`` turns a spec/concept into an :class:`OracleClaim` (a gated proposal). Async because a real
    oracle is a network/GPU call; an offline fake is async too."""

    name: str
    binding: ExternalBinding

    async def query(self, spec: Any) -> OracleClaim:
        ...


def oracle_claim_to_ledger(oc: OracleClaim, *, created_at: Optional[datetime] = None) -> Claim:
    """Convert an :class:`OracleClaim` into an **UNVERIFIED** ledger ``Claim`` carrying BOTH the binding's
    license provenance and the specific oracle-call provenance. Pure; :func:`record_oracle_claim` persists it.

    Status is UNVERIFIED by construction — an oracle answer is a proposal awaiting a deterministic gate, never
    a self-certified fact. This is the structural reason raw oracle truth cannot enter the ledger."""
    unc = "unknown" if oc.uncertainty is None else f"{oc.uncertainty:.3g}"
    val = "" if oc.value is None else f" value={oc.value:.6g} (±{unc})"
    text = (f"Oracle proposal [{oc.binding.name} v{oc.binding.version}, {oc.binding.license}]: "
            f"{oc.subject} -> {oc.statement}{val}")
    sources = [
        SourceRef(url_or_id=oc.oracle_provenance, retrieved=True, support=SourceSupport.SUPPORTS),
        SourceRef(url_or_id=oc.binding.provenance, retrieved=True, support=SourceSupport.SUPPORTS),
    ]
    return Claim(
        id=f"oracle:{oc.binding.name}:{oc.subject}",
        text=text,
        sources=sources,
        quote=None,
        status=ClaimStatus.UNVERIFIED,            # an oracle never self-certifies; a gate must verify it
        confidence=oc.confidence,
        verification=[],
        produced_by=f"external.oracle:{oc.binding.name}",
        model=f"{oc.binding.name}:{oc.binding.version}",
        created_at=created_at or datetime.now(timezone.utc),
    )


async def record_oracle_claim(
    store,
    oc: OracleClaim,
    *,
    run_id: str,
    created_at: Optional[datetime] = None,
) -> Claim:
    """The ONLY path from an oracle answer into the ledger: persist it as an UNVERIFIED claim with license +
    call provenance. There is deliberately no 'record a verified oracle fact' function — promotion is a gate's
    job. Returns the recorded claim."""
    claim = oracle_claim_to_ledger(oc, created_at=created_at)
    await store.add_claims(run_id, [claim])
    return claim


__all__ = ["OracleClaim", "ExternalOracle", "oracle_claim_to_ledger", "record_oracle_claim"]
