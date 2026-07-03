"""Phase χ — build the frontier map by pure synthesis of the proven phases (HORIZON §2C).

χ adds NO research and asks NO model: it assembles `state`'s already-gated outputs into an
honest map of the known (clusters of VERIFIED claims actually used in the report/solution/
spec) and the open frontier (the run's REAL surfaced gaps + REFUTED/UNSUPPORTED claims).
By construction the result passes GATE χ — and the gate re-checks it (defense in depth).

Deterministic, LLM-free, pure: same RunState -> same FrontierMap (reproducibility A5).
"""

from __future__ import annotations

from .core.state import (
    ClaimStatus,
    FrontierEdge,
    FrontierMap,
    KnownRegion,
    RunState,
)


def _used_fact_ids(state: RunState) -> list[str]:
    """Claim ids actually asserted across the gated phases, in deterministic order."""
    out: list[str] = []
    seen: set[str] = set()

    def add(cid: str) -> None:
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)

    if state.report is not None:
        for cid in state.report.statement_to_claim.values():
            add(cid)
    if state.solution_report is not None:
        for ap in state.solution_report.approaches:
            for cid in (*ap.grounding, *ap.tradeoffs):
                add(cid)
    if state.specification is not None:
        for cid in state.specification.claim_ids_used:
            add(cid)
    return out


def build_frontier_map(state: RunState, *, confidence_threshold: float = 0.7) -> FrontierMap:
    """Assemble a FrontierMap from a run's gated outputs. Pure, LLM-free, gate-passing.

    Known regions: one per VERIFIED+τ claim asserted in the report/solution/spec (labels are
    truncated claim text — human labels, not facts). Frontier edges: every surfaced gap of the
    run plus every REFUTED/UNSUPPORTED claim, each grounded in that real gap.
    """
    claims_by_id = {c.id: c for c in state.claims}

    known_regions: list[KnownRegion] = []
    for fid in _used_fact_ids(state):
        claim = claims_by_id.get(fid)
        if (
            claim is not None
            and claim.status is ClaimStatus.VERIFIED
            and claim.confidence >= confidence_threshold
        ):
            known_regions.append(
                KnownRegion(
                    id=f"region_{len(known_regions)}",
                    label=claim.text[:80],
                    fact_ids=[fid],
                )
            )

    edges: list[FrontierEdge] = []

    def add_gap_edges(gaps: list[str], category: str) -> None:
        for gap in gaps:
            if not gap.strip():
                continue  # an empty gap string is not a real gap — never an edge
            edges.append(
                FrontierEdge(
                    id=f"edge_{len(edges)}",
                    question=gap[:200],
                    grounded_in=gap,  # the gap text itself is the real grounding
                    category=category,
                )
            )

    if state.report is not None:
        add_gap_edges(state.report.gaps, "report_gap")
    if state.solution_report is not None:
        add_gap_edges(state.solution_report.gaps, "approach_gap")
    if state.specification is not None:
        add_gap_edges(state.specification.gaps, "spec_gap")

    for claim in state.claims:
        if claim.status in (ClaimStatus.REFUTED, ClaimStatus.UNSUPPORTED):
            edges.append(
                FrontierEdge(
                    id=f"edge_{len(edges)}",
                    question=claim.text[:200],
                    grounded_in=claim.id,  # the un-established claim is the real gap
                    category=claim.status.value,
                )
            )

    return FrontierMap(
        run_id=state.question.run_id,
        topic=state.question.raw,
        known_regions=known_regions,
        frontier_edges=edges,
        produced_by="cartographer",
    )


__all__ = ["build_frontier_map"]
