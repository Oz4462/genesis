"""Promotion gate + HITL ratification for the math-research branch (stone d-full).

Maps an IdentityArtifact onto the agreed epistemic ladder and enforces that ESTABLISHED
(a reusable deterministic-gate ANCHOR) is impossible without an explicit human sign-off.

Locked with the co-architect:
- Ladder: DISPROVED < WELL_FORMED < SUPPORTED < HARDENED < ESTABLISHED.
- Source of truth for 'proved' is ``proof.lean_status == 'cas_certified'`` (NOT proof_tier,
  which can drift). CAS-certified is NOT a Lean-kernel proof, so a CAS-certified identity is
  at most HARDENED autonomously — only a human SignOff promotes it to ESTABLISHED.
- SURVIVED_KNOWN (rediscovered) shares the same ceiling as SURVIVED_NOVEL: prior art is a
  citation, not a system-wide anchor proof.
- Refutation of an anchor cascades: the anchor -> DISPROVED, transitive dependents capped at
  HARDENED + flagged; independent anchors are untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from .identity_research import IdentityArtifact
from .ratification import RatificationItem, SignOff, is_ratified

Stage = Literal["DISPROVED", "WELL_FORMED", "SUPPORTED", "HARDENED", "ESTABLISHED"]
_SURVIVED = {"SURVIVED_NOVEL", "SURVIVED_KNOWN", "SURVIVED_NOVELTY_UNCHECKED"}
_ORDER = {"DISPROVED": 0, "WELL_FORMED": 1, "SUPPORTED": 2, "HARDENED": 3, "ESTABLISHED": 4}


def autonomous_stage(art: IdentityArtifact) -> Stage:
    """Highest stage the machine may assign WITHOUT human ratification (never ESTABLISHED)."""
    if art.status == "REFUTED":
        return "DISPROVED"
    if art.status in ("INCONCLUSIVE", "SURVIVED_NOVELTY_UNCHECKED"):
        return "WELL_FORMED"
    if art.status in ("SURVIVED_NOVEL", "SURVIVED_KNOWN"):
        if art.proof is not None and art.proof.lean_status == "cas_certified":
            return "HARDENED"
        return "SUPPORTED"
    return "WELL_FORMED"


def is_anchor(stage: Stage) -> bool:
    """Only an ESTABLISHED claim is a reusable deterministic-gate anchor."""
    return stage == "ESTABLISHED"


@dataclass(frozen=True)
class PromotionRecord:
    claim_ref: str
    from_stage: Stage
    to_stage: Stage
    lean_status: str
    proof_tier: int
    promoter: str                      # "autonomous" | "cascade" | approver identity
    signoff_ref: Optional[str] = None   # required iff to_stage == ESTABLISHED
    depends_on: tuple[str, ...] = ()
    promoted_at: str = ""
    note: str = ""


def _anchor_item(art: IdentityArtifact) -> RatificationItem:
    proof = art.proof.lean_status if art.proof else "no-proof"
    return RatificationItem(
        kind="anchor", ref=art.claim.claim_id,
        summary=f"{art.claim.lhs} = {art.claim.rhs} [{art.status}, {proof}]", blocking=True,
    )


def promote_to_established(
    art: IdentityArtifact, signoff: SignOff, *, depends_on: tuple[str, ...] = (), promoted_at: str = "",
) -> Optional[PromotionRecord]:
    """Promote to ESTABLISHED (a reusable anchor) — IMPOSSIBLE without both a cas_certified
    proof AND an explicit human sign-off approving this claim's ref. Returns None otherwise
    (the claim stays at its autonomous stage). CAS != Lean kernel, hence the human gate."""
    if art.status not in _SURVIVED:
        return None
    if art.proof is None or art.proof.lean_status != "cas_certified":
        return None
    if not is_ratified([_anchor_item(art)], signoff):
        return None
    return PromotionRecord(
        claim_ref=art.claim.claim_id, from_stage=autonomous_stage(art), to_stage="ESTABLISHED",
        lean_status=art.proof.lean_status, proof_tier=art.proof_tier,
        promoter=signoff.approver or "human", signoff_ref=signoff.approver,
        depends_on=tuple(depends_on), promoted_at=promoted_at,
        note="ratified anchor (CAS-certified + human sign-off; NOT Lean-kernel-verified)",
    )


class PromotionLedger:
    """Append-only promotion records + a dependency graph, with a refutation cascade."""

    def __init__(self) -> None:
        self._records: list[PromotionRecord] = []
        self._stage: dict[str, Stage] = {}
        self._depends_on: dict[str, tuple[str, ...]] = {}

    @property
    def records(self) -> list[PromotionRecord]:
        return list(self._records)

    def record(self, rec: PromotionRecord) -> None:
        self._records.append(rec)
        self._stage[rec.claim_ref] = rec.to_stage
        if rec.depends_on:
            self._depends_on[rec.claim_ref] = rec.depends_on

    def stage(self, ref: str) -> Optional[Stage]:
        return self._stage.get(ref)

    def is_anchor(self, ref: str) -> bool:
        return self._stage.get(ref) == "ESTABLISHED"

    def _append(self, ref: str, to_stage: Stage, promoter: str, note: str, promoted_at: str) -> None:
        self._records.append(PromotionRecord(
            claim_ref=ref, from_stage=self._stage.get(ref, "WELL_FORMED"), to_stage=to_stage,
            lean_status="", proof_tier=0, promoter=promoter, depends_on=self._depends_on.get(ref, ()),
            promoted_at=promoted_at, note=note,
        ))
        self._stage[ref] = to_stage

    def demote_refuted_anchor(self, claim_ref: str, *, promoted_at: str = "") -> list[str]:
        """The anchor -> DISPROVED; transitive dependents that are anchors are capped at
        HARDENED (+ flagged). Independent anchors are NOT touched. Returns demoted refs."""
        self._append(claim_ref, "DISPROVED", "cascade", "anchor refuted", promoted_at)
        demoted = [claim_ref]
        frontier, seen = [claim_ref], {claim_ref}
        while frontier:
            cur = frontier.pop()
            for ref, deps in self._depends_on.items():
                if cur in deps and ref not in seen:
                    seen.add(ref)
                    if _ORDER.get(self._stage.get(ref, "WELL_FORMED"), 1) > _ORDER["HARDENED"]:
                        self._append(ref, "HARDENED", "cascade", f"anchor_invalidated={claim_ref}", promoted_at)
                        demoted.append(ref)
                    frontier.append(ref)
        return demoted
