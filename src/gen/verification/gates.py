"""GATE α — the deterministic, LLM-free completion predicate for Phase α.

This is the enforcement point for the anti-hallucination guarantee. It is a pure
function over RunState: same input -> same result, no model calls, fully
unit-testable. See PHASE_ALPHA.md §4 for the conditions and §5 for the
acceptance criteria this implements.

Design note (from an independent adversarial audit): the gate is an INDEPENDENT
backstop. It does not trust the conductor to have only assembled sound reports —
it re-validates, for every asserted claim, that the claim has provenance and that
the asserted sentence actually matches the cited claim. Defense in depth: if a
future or buggy report builder ever asserts an unsourced or misattributed claim,
the gate catches it rather than trusting upstream.
"""

from __future__ import annotations

from ..core.interfaces import GateResult, GateFailure
from ..core.state import RunState, Claim, ClaimStatus


def claim_soundness_failures(
    claim: Claim,
    *,
    confidence_threshold: float,
    flagged: set[str],
) -> list[GateFailure]:
    """Per-claim α-soundness checks, shared by GATE α and GATE β.

    A claim asserted as support — for a fact (α) or for an Approach (β) — must:
    have provenance, not be REFUTED, meet τ if VERIFIED, only appear UNSUPPORTED if
    flagged as a gap, and cite only retrieved sources. Returns one GateFailure per
    violation (α codes), empty if sound. Pure; no model calls.

    `flagged` holds claim ids/texts explicitly surfaced as gaps, so an UNSUPPORTED
    claim shown honestly as a gap is permitted. Sharing this between both gates is
    deliberate defense in depth: β cannot weaken an α guarantee, because it re-runs
    the exact same per-claim check on every claim an approach leans on.
    """
    out: list[GateFailure] = []

    # Provenance backstop — asserted claim must have at least one source.
    if not claim.sources:
        out.append(
            GateFailure(
                code="UNSOURCED_CLAIM",
                detail=f"Asserted claim has no source: {claim.text!r}",
                claim_id=claim.id,
            )
        )

    # Refuted claims must not be asserted as fact/support.
    if claim.status is ClaimStatus.REFUTED:
        out.append(
            GateFailure(
                code="REFUTED_AS_FACT",
                detail=f"Refuted claim used as fact: {claim.text!r}",
                claim_id=claim.id,
            )
        )

    # Not-positively-verified claims (UNSUPPORTED *or* still UNVERIFIED) are allowed
    # ONLY if flagged as gaps. The gate is an independent backstop and must not trust
    # an upstream filter to have removed them — spec B-6 covers both statuses.
    if (
        claim.status in (ClaimStatus.UNSUPPORTED, ClaimStatus.UNVERIFIED)
        and claim.id not in flagged
        and claim.text not in flagged
    ):
        out.append(
            GateFailure(
                code="UNSUPPORTED_NOT_FLAGGED",
                detail=(
                    f"Not-verified claim ({claim.status.value}) asserted without flag: "
                    f"{claim.text!r}"
                ),
                claim_id=claim.id,
            )
        )

    # Verified claims must meet the confidence threshold.
    if claim.status is ClaimStatus.VERIFIED and claim.confidence < confidence_threshold:
        out.append(
            GateFailure(
                code="LOW_CONFIDENCE",
                detail=(
                    f"Verified claim below τ={confidence_threshold}: "
                    f"{claim.confidence:.2f} — {claim.text!r}"
                ),
                claim_id=claim.id,
            )
        )

    # Every cited source must have been retrieved (no dead citation).
    for ref in (*claim.sources, *claim.verification):
        if not ref.retrieved:
            out.append(
                GateFailure(
                    code="DEAD_CITATION",
                    detail=f"Cited source not retrieved: {ref.url_or_id!r}",
                    claim_id=claim.id,
                )
            )

    return out


def gate_alpha(
    state: RunState,
    *,
    confidence_threshold: float = 0.7,
) -> GateResult:
    """Decide whether the Phase α report may be delivered.

    Conditions (all must hold) over the claims actually asserted in the report:
      1. No hidden facts        — every sentence maps to an existing claim.
      1b. No misattribution     — the sentence text matches the cited claim's text.
      1c. Provenance backstop   — every asserted claim has >= 1 source.
      2. No REFUTED-as-fact     — refuted claims never presented as true.
      3. UNSUPPORTED flagged     — unbacked claims appear only if marked.
      4. Min confidence          — VERIFIED claims meet threshold τ.
      5. Live citations          — every cited source was actually retrieved.

    Returns a GateResult with every failure enumerated, so the conductor can
    decide per item: re-research or surface as an explicit gap.
    """
    failures: list[GateFailure] = []
    report = state.report

    if report is None:
        return GateResult(
            gate="alpha",
            passed=False,
            failures=[GateFailure(code="NO_REPORT", detail="Report not assembled.")],
        )

    claims_by_id = {c.id: c for c in state.claims}

    # Condition 1 / 1b: every mapped sentence references an existing claim, and
    # the asserted sentence must match that claim's text (no misattribution).
    for sentence, claim_id in report.statement_to_claim.items():
        claim = claims_by_id.get(claim_id)
        if claim is None:
            failures.append(
                GateFailure(
                    code="UNSOURCED_STATEMENT",
                    detail=f"Sentence maps to unknown claim {claim_id!r}: {sentence!r}",
                    claim_id=claim_id,
                )
            )
            continue
        if sentence != claim.text:
            failures.append(
                GateFailure(
                    code="SENTENCE_CLAIM_MISMATCH",
                    detail=(
                        f"Asserted sentence does not match claim {claim_id!r}: "
                        f"{sentence!r} != {claim.text!r}"
                    ),
                    claim_id=claim_id,
                )
            )

    # Conditions 1c-5 over the claims actually asserted in the report — delegated to
    # the shared per-claim soundness check (identical logic, now reused by GATE β so
    # the two gates can never drift apart).
    used_ids = set(report.statement_to_claim.values())
    flagged = set(report.gaps)
    for claim in state.claims:
        if claim.id not in used_ids:
            continue  # claim exists but is not asserted in the report body
        failures.extend(
            claim_soundness_failures(
                claim, confidence_threshold=confidence_threshold, flagged=flagged
            )
        )

    return GateResult(gate="alpha", passed=not failures, failures=failures)


def gate_beta(
    state: RunState,
    *,
    confidence_threshold: float = 0.7,
) -> GateResult:
    """GATE β — the deterministic, LLM-free completion predicate for Phase β.

    Decides whether the solution-space report (``state.solution_report``) may be
    delivered. The β guarantee: every asserted Approach is anchored in at least one
    VERIFIED claim (no fabricated approach), and every claim an approach leans on —
    grounding or trade-off — is α-sound. β never weakens α: it re-runs the shared
    per-claim soundness check on every referenced claim. See PHASE_BETA.md §4/§5.

    Conditions (all must hold) over the approaches asserted in the report:
      B-1 UNGROUNDED_APPROACH      — every approach has >= 1 grounding claim.
      B-2 GROUNDING_UNKNOWN_CLAIM  — every grounding id exists in the ledger.
      B-3 GROUNDING_NOT_VERIFIED   — every grounding claim is VERIFIED and meets τ.
      B-5 TRADEOFF_UNKNOWN_CLAIM   — every trade-off id exists in the ledger.
      (shared α-soundness)         — UNSOURCED_CLAIM / REFUTED_AS_FACT /
                                     UNSUPPORTED_NOT_FLAGGED / LOW_CONFIDENCE /
                                     DEAD_CITATION on every referenced claim.

    Abstention (no groundable approach -> zero approaches asserted) passes: nothing
    unverified is claimed. The false-uniqueness trap is caught by the same machinery
    as α — the "only way" claim is REFUTED and rejected by REFUTED_AS_FACT, while the
    synthesizer surfaces the real alternatives.
    """
    report = state.solution_report
    if report is None:
        return GateResult(
            gate="beta",
            passed=False,
            failures=[
                GateFailure(
                    code="NO_SOLUTION_REPORT",
                    detail="Solution report not assembled.",
                )
            ],
        )

    claims_by_id = {c.id: c for c in state.claims}
    flagged = set(report.gaps)
    failures: list[GateFailure] = []

    for ap in report.approaches:
        # B-1: structural grounding requirement. The Approach constructor already
        # guards this; the gate refuses to trust upstream and backstops it here.
        if not ap.grounding:
            failures.append(
                GateFailure(
                    code="UNGROUNDED_APPROACH",
                    detail=f"Approach {ap.name!r} has no grounding claim.",
                    claim_id=ap.id,
                )
            )

        for cid in ap.grounding:
            claim = claims_by_id.get(cid)
            if claim is None:
                failures.append(
                    GateFailure(
                        code="GROUNDING_UNKNOWN_CLAIM",
                        detail=f"Approach {ap.name!r} grounded in unknown claim {cid!r}.",
                        claim_id=cid,
                    )
                )
                continue
            # B-3 — the heart of β: grounding must be VERIFIED and meet the threshold.
            # An approach grounded only in an unverified/unsupported claim is exactly a
            # fabricated approach, and is rejected here.
            if claim.status is not ClaimStatus.VERIFIED:
                failures.append(
                    GateFailure(
                        code="GROUNDING_NOT_VERIFIED",
                        detail=(
                            f"Approach {ap.name!r} grounded in non-verified claim "
                            f"({claim.status.value}): {claim.text!r}"
                        ),
                        claim_id=cid,
                    )
                )
            elif claim.confidence < confidence_threshold:
                failures.append(
                    GateFailure(
                        code="GROUNDING_NOT_VERIFIED",
                        detail=(
                            f"Approach {ap.name!r} grounded in under-confident claim "
                            f"({claim.confidence:.2f} < τ={confidence_threshold}): "
                            f"{claim.text!r}"
                        ),
                        claim_id=cid,
                    )
                )
            # Shared α-soundness (provenance, refuted, dead citation, ...) for grounding.
            failures.extend(
                claim_soundness_failures(
                    claim, confidence_threshold=confidence_threshold, flagged=flagged
                )
            )

        for cid in ap.tradeoffs:
            claim = claims_by_id.get(cid)
            if claim is None:
                failures.append(
                    GateFailure(
                        code="TRADEOFF_UNKNOWN_CLAIM",
                        detail=(
                            f"Approach {ap.name!r} trade-off references unknown claim "
                            f"{cid!r}."
                        ),
                        claim_id=cid,
                    )
                )
                continue
            # Trade-offs are factual properties — each must be α-sound. An UNSUPPORTED
            # trade-off is allowed only if flagged as a gap (honest comparison).
            failures.extend(
                claim_soundness_failures(
                    claim, confidence_threshold=confidence_threshold, flagged=flagged
                )
            )

    return GateResult(gate="beta", passed=not failures, failures=failures)
