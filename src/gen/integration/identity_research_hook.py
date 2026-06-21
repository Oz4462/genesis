"""Side-channel math-research hook for a run (stone 1, dual-agent locked).

Runs the (synchronous) math-research assessment over EXPLICIT, structured proposals as an
async side channel — bridged with ``asyncio.to_thread`` so it never blocks the event loop.

Locked decisions (Claude agents + Grok converged):
- This is a gen.integration POST-HOOK, default-OFF — it is NOT wired into the conductor
  refine loop. IdentityArtifacts use a different verification model (SURVIVED_* != VERIFIED),
  so they must never feed GATE α nor raise any Claim to VERIFIED.
- Identities arrive as STRUCTURED ``IdentityProposal``s (a proposer's job), never parsed
  from free-text claim bodies with a regex/'=' heuristic.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from ..core.state import RunState
from ..identity_research import (
    AssumptionManifest,
    IdentityArtifact,
    NoveltyBackend,
    assess_identity,
    assess_inequality,
    persist_identity_artifact,
)


@dataclass(frozen=True)
class IdentityProposal:
    """A structured candidate for math-research (never inferred from free text)."""

    claim_id: str
    lhs: str
    rhs: str
    manifest: AssumptionManifest
    relation: str = "eq"   # "eq" -> assess_identity; ge|gt|le|lt -> assess_inequality


def _assess_one(p: IdentityProposal, novelty_index: Optional[NoveltyBackend], n_samples: int) -> IdentityArtifact:
    if p.relation == "eq":
        return assess_identity(p.claim_id, p.lhs, p.rhs, p.manifest,
                               novelty_index=novelty_index, n_samples=n_samples)
    return assess_inequality(p.claim_id, p.lhs, p.rhs, p.relation, p.manifest,
                             novelty_index=novelty_index, n_samples=n_samples)


async def enrich_run_with_identity_research(
    state: RunState, proposals: list[IdentityProposal], *,
    novelty_index: Optional[NoveltyBackend] = None, persist: bool = True, n_samples: int = 300,
) -> list[IdentityArtifact]:
    """Assess each structured proposal off the event loop and append an honest log line.

    Returns the artifacts. Does NOT touch ``state.claims`` or any Claim status — the
    math-research branch is a side channel, not a ledger upgrade (default-off integration)."""
    artifacts: list[IdentityArtifact] = []
    for p in proposals:
        art = await asyncio.to_thread(_assess_one, p, novelty_index, n_samples)
        if persist:
            await asyncio.to_thread(persist_identity_artifact, art)
        proof = art.proof.lean_status if art.proof else "no-proof"
        state.log.append(f"identity_research: {p.claim_id} -> {art.status} [{proof}]")
        artifacts.append(art)
    return artifacts
