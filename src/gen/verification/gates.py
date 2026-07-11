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

import math
import re
from collections.abc import Sequence

from ..core.errors import FormulaError, GeometryError, UnitError
from ..core.interfaces import GateResult, GateFailure
from ..core.state import (
    CONSTRAINT_KINDS,
    GEOMETRY_OPERATIONS,
    GEOMETRY_PRIMITIVES,
    GEOMETRY_TRANSFORMS,
    Claim,
    ClaimStatus,
    Divergence,
    FrontierMap,
    GeometryNode,
    Pin,
    PinType,
    Quantity,
    RunState,
    ValueOrigin,
)
from .derivation import (
    DEFAULT_TOLERANCE,
    evaluate_formula,
    is_numeric_literal,
    referenced_names,
    topological_values,
    within_tolerance,
)
from .geometry import aabb_of, overlaps
from .units import Dimension, formula_dimension, parse_unit, unit_scale
from ..uncertainty import combine_standard_uncertainty
from ..software import SUPPORTED_LANGUAGES, run_python_artifact


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
    # Non-finite confidence is a separate poison class: ``NaN < τ`` is always
    # False in IEEE floats, so a naive comparison would *pass* VERIFIED+NaN.
    # Post-construction mutation can still inject NaN (Claim is not frozen);
    # the gate is the last structural backstop (REWORK 2026-07-11).
    if claim.status is ClaimStatus.VERIFIED:
        conf = claim.confidence
        if (
            isinstance(conf, bool)
            or not isinstance(conf, (int, float))
            or not math.isfinite(conf)
        ):
            out.append(
                GateFailure(
                    code="NONFINITE_CONFIDENCE",
                    detail=(
                        f"Verified claim has non-finite confidence {conf!r}: "
                        f"{claim.text!r}"
                    ),
                    claim_id=claim.id,
                )
            )
        elif conf < confidence_threshold:
            out.append(
                GateFailure(
                    code="LOW_CONFIDENCE",
                    detail=(
                        f"Verified claim below τ={confidence_threshold}: "
                        f"{conf:.2f} — {claim.text!r}"
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


# --- GATE γ -------------------------------------------------------------------

def _value_render_candidates(value: float) -> list[str]:
    """Textual renderings under which a numeric value may appear in a claim.

    Kept deliberately literal (integer and decimal form): a GROUNDED value must
    match the source wording — unit conversions are DERIVED quantities with a
    recomputable formula, never a silent rewrite (PHASE_GAMMA.md §0).
    """
    v = float(value)
    candidates = {f"{v:g}", str(value)}
    if v.is_integer():
        candidates.add(str(int(v)))
        candidates.add(f"{v:.1f}")  # "50.0"
    return sorted(candidates)


def value_in_text(value: float, text: str) -> bool:
    """True if `value` appears in `text` as a standalone number (C-4).

    Digit-boundary-guarded so 5 never matches inside 15 or 0.5 inside 10.5 —
    a sloppy substring match would let fabricated values borrow digits from
    unrelated numbers in the source. The boundary also rejects a leading '-', so a
    positive value never matches a negative number (a +3 claim cannot be "verified"
    against a source that only states -3) — the sign is part of the value (C-4).
    """
    for cand in _value_render_candidates(value):
        pattern = r"(?<![\d.\-])" + re.escape(cand) + r"(?![\d.])"
        if re.search(pattern, text):
            return True
    return False


def _check_geometry(
    node: GeometryNode,
    *,
    component_name: str,
    quantities: dict[str, Quantity],
    failures: list[GateFailure],
) -> None:
    """Recursive C-8/C-9 walk over one CSG tree (pure, no model calls)."""
    where = f"component {component_name!r}, geometry {node.kind!r}"

    if node.kind in GEOMETRY_PRIMITIVES:
        required = set(GEOMETRY_PRIMITIVES[node.kind])
        if set(node.params) != required:
            failures.append(
                GateFailure(
                    code="INVALID_GEOMETRY",
                    detail=(
                        f"{where}: params must be exactly {sorted(required)}, "
                        f"got {sorted(node.params)}"
                    ),
                )
            )
        if node.children:
            failures.append(
                GateFailure(
                    code="INVALID_GEOMETRY",
                    detail=f"{where}: a primitive must not have children",
                )
            )
        for pname, qid in node.params.items():
            quantity = quantities.get(qid)
            if quantity is None:
                failures.append(
                    GateFailure(
                        code="DANGLING_REFERENCE",
                        detail=f"{where}: param {pname!r} references unknown quantity {qid!r}",
                    )
                )
            elif pname in required and float(quantity.value) <= 0.0:
                failures.append(
                    GateFailure(
                        code="INVALID_GEOMETRY",
                        detail=(
                            f"{where}: dimension {pname!r} must be > 0, "
                            f"got {quantity.value} ({qid})"
                        ),
                    )
                )
        return

    if node.kind in GEOMETRY_OPERATIONS:
        if node.params:
            failures.append(
                GateFailure(
                    code="INVALID_GEOMETRY",
                    detail=f"{where}: an operation takes no params",
                )
            )
        if len(node.children) < 2:
            failures.append(
                GateFailure(
                    code="INVALID_GEOMETRY",
                    detail=f"{where}: an operation needs >= 2 children",
                )
            )
        for child in node.children:
            _check_geometry(
                child,
                component_name=component_name,
                quantities=quantities,
                failures=failures,
            )
        return

    if node.kind in GEOMETRY_TRANSFORMS:
        required = set(GEOMETRY_TRANSFORMS[node.kind])
        if set(node.params) != required:
            failures.append(
                GateFailure(
                    code="INVALID_GEOMETRY",
                    detail=(
                        f"{where}: params must be exactly {sorted(required)}, "
                        f"got {sorted(node.params)}"
                    ),
                )
            )
        if len(node.children) != 1:
            failures.append(
                GateFailure(
                    code="INVALID_GEOMETRY",
                    detail=f"{where}: a transform needs exactly 1 child",
                )
            )
        for pname, qid in node.params.items():
            if qid not in quantities:
                failures.append(
                    GateFailure(
                        code="DANGLING_REFERENCE",
                        detail=f"{where}: param {pname!r} references unknown quantity {qid!r}",
                    )
                )
        for child in node.children:
            _check_geometry(
                child,
                component_name=component_name,
                quantities=quantities,
                failures=failures,
            )
        return

    failures.append(
        GateFailure(
            code="INVALID_GEOMETRY",
            detail=f"{where}: unknown geometry kind {node.kind!r}",
        )
    )


def _normalize(text: str) -> str:
    """Lower-case + collapse whitespace, for robust substring matching."""
    return " ".join(text.lower().split())


def text_in_claim(needle: str, claim_text: str) -> bool:
    """True if `needle` appears (normalized substring) in a claim's text. The
    string analogue of value_in_text (C-4): a supplier/part name asserted in a
    sourcing must literally come from a verified claim, not be invented."""
    n = _normalize(needle)
    return bool(n) and n in _normalize(claim_text)


def _check_sourcing(item, *, quantities, check_claim_ref, failures) -> None:
    """C-16: a BOM sourcing must be claim-backed — supplier and part_number
    appear verbatim in a grounding claim, the grounding is VERIFIED/α-sound, and
    the price (if any) is a GROUNDED quantity (verbatim number via C-1..C-4)."""
    src = item.sourcing
    if not src.grounding:
        failures.append(
            GateFailure(
                code="SOURCING_NOT_GROUNDED",
                detail=f"BOM item {item.id!r} sourcing has no grounding claim.",
            )
        )
        return
    grounding_claims = []
    for cid in src.grounding:
        claim = check_claim_ref(cid, f"BOM item {item.id!r} sourcing")
        if claim is not None:
            grounding_claims.append(claim)
            if claim.status is not ClaimStatus.VERIFIED:
                failures.append(
                    GateFailure(
                        code="SOURCING_NOT_GROUNDED",
                        detail=(
                            f"BOM item {item.id!r} sourcing grounded in non-verified "
                            f"claim ({claim.status.value}): {claim.text!r}"
                        ),
                        claim_id=cid,
                    )
                )
    # supplier & part_number must each appear in some grounding claim's text
    for field_name, value in (("supplier", src.supplier), ("part_number", src.part_number)):
        if value and not any(text_in_claim(value, c.text) for c in grounding_claims):
            failures.append(
                GateFailure(
                    code="SOURCING_NOT_IN_CLAIM",
                    detail=(
                        f"BOM item {item.id!r} sourcing {field_name} {value!r} does not "
                        "appear in any grounding claim — no invented shop/part."
                    ),
                )
            )
    # the price must be a GROUNDED quantity (its number is then verbatim-checked
    # against its own claim by C-1..C-4 in the quantity loop)
    if src.price_quantity_id is not None:
        price_q = quantities.get(src.price_quantity_id)
        if price_q is None:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=(
                        f"BOM item {item.id!r} sourcing price references unknown "
                        f"quantity {src.price_quantity_id!r}"
                    ),
                )
            )
        elif price_q.origin is not ValueOrigin.GROUNDED:
            failures.append(
                GateFailure(
                    code="SOURCING_NOT_GROUNDED",
                    detail=(
                        f"BOM item {item.id!r} price {src.price_quantity_id!r} must be a "
                        "GROUNDED quantity (its number verbatim from a claim), not "
                        f"{price_q.origin.value}."
                    ),
                )
            )


def gate_phi(
    divergence: Divergence,
    claims: Sequence[Claim],
    *,
    confidence_threshold: float = 0.7,
) -> GateResult:
    """GATE φ — the deterministic, LLM-free completion predicate for Phase φ.

    Divergence has no completeness gate (a possibility space cannot be proven whole),
    so φ enforces the only honest guarantee instead (HORIZON.md §3/§5):

      P-1 UNGROUNDED_POSSIBILITY    — every possibility has >= 1 grounding
                                      (the constructor guards it; the gate backstops).
      P-2 GROUNDING_UNKNOWN_CLAIM   — every grounding id exists in the ledger.
      P-3 GROUNDING_NOT_VERIFIED    — every grounding claim is VERIFIED and meets τ
                                      (no invented neighbourhood — same DNA as α/β).
      P-4 NOT_GROUNDED_SAMPLE       — the divergence is honestly marked as a grounded
                                      sample, never as the whole space.

    Abstention (zero possibilities) passes: nothing invented is asserted. Pure; no
    model calls; same-input -> same-result (reproducibility A5).
    """
    claims_by_id = {c.id: c for c in claims}
    failures: list[GateFailure] = []

    # P-4: the loud honesty disclaimer is non-negotiable — claiming completeness
    # (grounded_sample False) is structurally rejected, even with zero possibilities.
    if not divergence.grounded_sample:
        failures.append(
            GateFailure(
                code="NOT_GROUNDED_SAMPLE",
                detail=(
                    "Divergence must be marked as a grounded sample, not the whole "
                    "possibility space (HORIZON.md §3)."
                ),
            )
        )

    for poss in divergence.possibilities:
        # P-1: structural grounding requirement (constructor guards; gate backstops).
        if not poss.grounding:
            failures.append(
                GateFailure(
                    code="UNGROUNDED_POSSIBILITY",
                    detail=f"Possibility {poss.statement!r} has no grounding.",
                    claim_id=poss.id,
                )
            )

        for cid in poss.grounding:
            claim = claims_by_id.get(cid)
            if claim is None:
                failures.append(
                    GateFailure(
                        code="GROUNDING_UNKNOWN_CLAIM",
                        detail=f"Possibility {poss.statement!r} grounded in unknown claim {cid!r}.",
                        claim_id=cid,
                    )
                )
                continue
            # P-3 — the heart of φ: an anchor must be VERIFIED and meet the threshold.
            # A possibility anchored only in an unverified claim is an invented
            # neighbourhood, and is rejected here.
            if claim.status is not ClaimStatus.VERIFIED:
                failures.append(
                    GateFailure(
                        code="GROUNDING_NOT_VERIFIED",
                        detail=(
                            f"Possibility {poss.statement!r} anchored in non-verified claim "
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
                            f"Possibility {poss.statement!r} anchored in under-confident claim "
                            f"({claim.confidence:.2f} < τ={confidence_threshold}): {claim.text!r}"
                        ),
                        claim_id=cid,
                    )
                )

    return GateResult(gate="phi", passed=not failures, failures=failures)


def gate_chi(
    state: RunState,
    frontier_map: FrontierMap,
    *,
    confidence_threshold: float = 0.7,
) -> GateResult:
    """GATE χ — the deterministic, LLM-free completion predicate for Phase χ.

    χ is a pure synthesis of the proven phases — it may neither fabricate knowledge nor
    invent a gap. The map is honest iff (HORIZON.md §2C):

      CHI-1 KNOWN_UNVERIFIED     — every fact_id in a known region is VERIFIED and meets τ.
      CHI-2 KNOWN_UNKNOWN_CLAIM  — every fact_id exists in the ledger.
      CHI-3 FRONTIER_NOT_GROUNDED — every frontier edge's `grounded_in` matches a REAL gap
                                    of the run (a surfaced gap from report/solution/spec, or
                                    a REFUTED/UNSUPPORTED claim id/text). No invented gaps.

    Abstention (empty known regions, edges all grounded) passes: an honest "we mapped the
    open questions". Pure; no model calls; same input -> same result (A5).
    """
    claims_by_id = {c.id: c for c in state.claims}
    failures: list[GateFailure] = []

    for region in frontier_map.known_regions:
        if not region.fact_ids:  # constructor guards; gate backstops
            failures.append(
                GateFailure(code="KNOWN_UNVERIFIED", detail=f"region {region.id!r} anchors no fact.")
            )
        for fid in region.fact_ids:
            claim = claims_by_id.get(fid)
            if claim is None:
                failures.append(
                    GateFailure(
                        code="KNOWN_UNKNOWN_CLAIM",
                        detail=f"region {region.id!r} references unknown claim {fid!r}.",
                        claim_id=fid,
                    )
                )
                continue
            if claim.status is not ClaimStatus.VERIFIED:
                failures.append(
                    GateFailure(
                        code="KNOWN_UNVERIFIED",
                        detail=(
                            f"region {region.id!r} claims fact {fid!r} but status is "
                            f"{claim.status.value}, not VERIFIED."
                        ),
                        claim_id=fid,
                    )
                )
            elif claim.confidence < confidence_threshold:
                failures.append(
                    GateFailure(
                        code="KNOWN_UNVERIFIED",
                        detail=(
                            f"region {region.id!r} claims fact {fid!r} but confidence "
                            f"{claim.confidence:.2f} < τ={confidence_threshold}."
                        ),
                        claim_id=fid,
                    )
                )

    # CHI-3: the set of REAL gaps this run actually surfaced — an edge may ground only here.
    # Empty/whitespace strings are never real gaps (an upstream empty gap must not become a
    # valid anchor for a fabricated edge).
    real_gaps: set[str] = set()

    def _add_gap(value: str) -> None:
        if value and value.strip():
            real_gaps.add(value)

    if state.report is not None:
        for g in state.report.gaps:
            _add_gap(g)
    if state.solution_report is not None:
        for g in state.solution_report.gaps:
            _add_gap(g)
    if state.specification is not None:
        for g in state.specification.gaps:
            _add_gap(g)
    for claim in state.claims:
        if claim.status in (ClaimStatus.REFUTED, ClaimStatus.UNSUPPORTED):
            _add_gap(claim.id)
            _add_gap(claim.text)

    for edge in frontier_map.frontier_edges:
        if edge.grounded_in not in real_gaps:
            failures.append(
                GateFailure(
                    code="FRONTIER_NOT_GROUNDED",
                    detail=(
                        f"frontier edge {edge.id!r} ({edge.question!r}) grounds in "
                        f"{edge.grounded_in!r}, which is not a real gap of this run "
                        "(invented edge)."
                    ),
                    claim_id=edge.id,
                )
            )

    return GateResult(gate="chi", passed=not failures, failures=failures)


def gate_gamma(
    state: RunState,
    *,
    confidence_threshold: float = 0.7,
    derivation_tolerance: float = DEFAULT_TOLERANCE,
) -> GateResult:
    """GATE γ — the deterministic, LLM-free completion predicate for Phase γ.

    Decides whether the specification (``state.specification``) may be
    delivered. The γ guarantee covers the five hallucination faces of a build
    plan (PHASE_GAMMA.md §0/§5) — every condition is pure code, defense in
    depth, trusting neither the `architect` nor any constructor guard:

      Wert         C-1 UNGROUNDED_VALUE, C-2 VALUE_UNKNOWN_CLAIM,
                   C-3 VALUE_NOT_VERIFIED, C-4 VALUE_NOT_IN_GROUNDING,
                   C-5 shared α-soundness on every referenced claim
      Rechnung     C-6 BROKEN_DERIVATION (independent recompute, topological)
      Entscheidung C-7 UNDECLARED_DECISION
      Drift        C-8 DANGLING_REFERENCE (incl. duplicate ids),
                   C-9 INVALID_GEOMETRY
      Vollständig  C-10 INCOMPLETE_STEP, C-11 UNBUILDABLE_ORDER
      Maß          C-12 UNIT_MISMATCH, C-13 CONSTRAINT_VIOLATION (constraints
                   are arithmetic expressions over quantity_ids, e.g.
                   "q_t >= 0.1 * q_w" or "q_t > 0"),
                   C-15 DIMENSION_MISMATCH (derivations are dimensionally
                   homogeneous; the Mars-Climate-Orbiter guard, Kennedy 2009)
      Konsistenz   C-17 CROSS_CLAIM_CONFLICT (two quantities tagged with the same
                   declared `measurand` must agree — same dimension and same value
                   after unit conversion; a deterministic contradiction-between-
                   accepted-facts guard, no language understanding)
      Unsicherheit C-18 BROKEN_UNCERTAINTY (a DERIVED quantity's declared standard
                   uncertainty must independently recompute from its inputs by the
                   GUM law of propagation, JCGM 100; code computes, gate recomputes)
      β-Kette      C-14 SPEC_NOT_ANCHORED

    Abstention (nothing groundable -> empty specification + explicit gaps)
    passes: nothing unverified is asserted — the exact α/β pattern.
    """
    spec = state.specification
    if spec is None:
        return GateResult(
            gate="gamma",
            passed=False,
            failures=[
                GateFailure(
                    code="NO_SPECIFICATION",
                    detail="Specification not assembled.",
                )
            ],
        )

    failures: list[GateFailure] = []
    claims_by_id = {c.id: c for c in state.claims}
    flagged = set(spec.gaps)

    def check_claim_ref(cid: str, context: str) -> Claim | None:
        claim = claims_by_id.get(cid)
        if claim is None:
            failures.append(
                GateFailure(
                    code="VALUE_UNKNOWN_CLAIM",
                    detail=f"{context} references unknown claim {cid!r}.",
                    claim_id=cid,
                )
            )
            return None
        failures.extend(
            claim_soundness_failures(
                claim,
                confidence_threshold=confidence_threshold,
                flagged=flagged,
            )
        )
        return claim

    # --- id namespaces; duplicates are drift (C-8) -----------------------------
    quantities: dict[str, Quantity] = {}
    for q in spec.quantities:
        if q.id in quantities:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=f"duplicate quantity id {q.id!r}",
                )
            )
            continue
        quantities[q.id] = q

    component_ids: set[str] = set()
    for comp in spec.components:
        if comp.id in component_ids:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=f"duplicate component id {comp.id!r}",
                )
            )
        component_ids.add(comp.id)

    bom_ids: set[str] = set()
    for item in spec.bom:
        if item.id in bom_ids:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=f"duplicate BOM id {item.id!r}",
                )
            )
        bom_ids.add(item.id)

    # Unit -> Dimension cache, shared by the constraint section (C-13) and the
    # derivation dimensional check (C-15). Returns None for an unparseable unit.
    unit_dim_cache: dict[str, Dimension | None] = {}

    def _dim_of_unit(unit: str) -> Dimension | None:
        if unit not in unit_dim_cache:
            try:
                unit_dim_cache[unit] = parse_unit(unit)
            except UnitError:
                unit_dim_cache[unit] = None
        return unit_dim_cache[unit]

    # --- Wert: C-1..C-5 over quantities ----------------------------------------
    for q in quantities.values():
        if q.origin is ValueOrigin.GROUNDED:
            if not q.grounding:
                failures.append(
                    GateFailure(
                        code="UNGROUNDED_VALUE",
                        detail=f"GROUNDED quantity {q.id!r} ({q.name!r}) has no grounding claim.",
                    )
                )
                continue
            literal_match = False
            for cid in q.grounding:
                claim = check_claim_ref(cid, f"quantity {q.id!r}")
                if claim is None:
                    continue
                if claim.status is not ClaimStatus.VERIFIED:
                    failures.append(
                        GateFailure(
                            code="VALUE_NOT_VERIFIED",
                            detail=(
                                f"quantity {q.id!r} grounded in non-verified claim "
                                f"({claim.status.value}): {claim.text!r}"
                            ),
                            claim_id=cid,
                        )
                    )
                elif claim.confidence < confidence_threshold:
                    failures.append(
                        GateFailure(
                            code="VALUE_NOT_VERIFIED",
                            detail=(
                                f"quantity {q.id!r} grounded in under-confident claim "
                                f"({claim.confidence:.2f} < τ={confidence_threshold}): "
                                f"{claim.text!r}"
                            ),
                            claim_id=cid,
                        )
                    )
                if value_in_text(float(q.value), claim.text):
                    literal_match = True
            if not literal_match and any(cid in claims_by_id for cid in q.grounding):
                failures.append(
                    GateFailure(
                        code="VALUE_NOT_IN_GROUNDING",
                        detail=(
                            f"value {q.value} of quantity {q.id!r} ({q.name!r}) does not "
                            "appear literally in any grounding claim text — a converted "
                            "or adjusted value must be DERIVED, not GROUNDED."
                        ),
                    )
                )
        elif q.origin is ValueOrigin.DECISION:
            # C-7 backstop (constructor guards, gate re-checks).
            if not q.rationale.strip():
                failures.append(
                    GateFailure(
                        code="UNDECLARED_DECISION",
                        detail=f"DECISION quantity {q.id!r} ({q.name!r}) has no rationale.",
                    )
                )

    # --- Rechnung: C-6 independent recompute ------------------------------------
    known = {
        q.id: float(q.value)
        for q in quantities.values()
        if q.origin is not ValueOrigin.DERIVED
    }
    derived_map = {}
    for q in quantities.values():
        if q.origin is not ValueOrigin.DERIVED:
            continue
        if q.derivation is None:
            failures.append(
                GateFailure(
                    code="BROKEN_DERIVATION",
                    detail=f"DERIVED quantity {q.id!r} has no derivation to recompute.",
                )
            )
            continue
        derived_map[q.id] = q.derivation
    computed, derivation_errors = topological_values(known, derived_map)
    for qid, reason in sorted(derivation_errors.items()):
        failures.append(
            GateFailure(
                code="BROKEN_DERIVATION",
                detail=f"DERIVED quantity {qid!r} cannot be recomputed: {reason}",
            )
        )
    for qid in derived_map:
        if qid in derivation_errors:
            continue
        stated = float(quantities[qid].value)
        if not within_tolerance(stated, computed[qid], tolerance=derivation_tolerance):
            failures.append(
                GateFailure(
                    code="BROKEN_DERIVATION",
                    detail=(
                        f"DERIVED quantity {qid!r} does not recompute: stated "
                        f"{stated}, computed {computed[qid]} "
                        f"(formula {derived_map[qid].formula!r})"
                    ),
                )
            )

    # --- Entscheidung: C-7 over the decision sheet -------------------------------
    decision_ids: set[str] = set()
    for d in spec.decisions:
        if d.id in decision_ids:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=f"duplicate decision id {d.id!r}",
                )
            )
        decision_ids.add(d.id)
        if not d.choice.strip() or not d.rationale.strip():
            failures.append(
                GateFailure(
                    code="UNDECLARED_DECISION",
                    detail=f"decision {d.id!r} ({d.title!r}) lacks choice or rationale.",
                )
            )
        for cid in d.informed_by:
            check_claim_ref(cid, f"decision {d.id!r}")

    # --- Drift: C-8 reference resolution -----------------------------------------
    for comp in spec.components:
        for qid in comp.quantity_ids:
            if qid not in quantities:
                failures.append(
                    GateFailure(
                        code="DANGLING_REFERENCE",
                        detail=f"component {comp.id!r} references unknown quantity {qid!r}",
                    )
                )
        if comp.material_density is not None and comp.material_density not in quantities:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=(
                        f"component {comp.id!r} material_density references unknown "
                        f"quantity {comp.material_density!r}"
                    ),
                )
            )
        if comp.geometry is not None:
            _check_geometry(
                comp.geometry,
                component_name=comp.name,
                quantities=quantities,
                failures=failures,
            )

    for item in spec.bom:
        if item.component_id is not None and item.component_id not in component_ids:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=f"BOM item {item.id!r} references unknown component {item.component_id!r}",
                )
            )
        if item.count < 1:
            failures.append(
                GateFailure(
                    code="INCOMPLETE_STEP",
                    detail=f"BOM item {item.id!r} ({item.name!r}) has count < 1.",
                )
            )
        for cid in item.grounding:
            check_claim_ref(cid, f"BOM item {item.id!r}")

        # C-16: sourcing (supplier/part/price) must be claim-backed — no invented
        # shop, order number, or price.
        if item.sourcing is not None:
            _check_sourcing(
                item,
                quantities=quantities,
                check_claim_ref=check_claim_ref,
                failures=failures,
            )

    # (constraint reference resolution is handled in the unified constraint
    #  section below, since left/right are now arithmetic expressions, C-13)

    # --- Vollständigkeit: C-10/C-11 over the steps --------------------------------
    seen_indexes: set[int] = set()
    step_ids: set[str] = set()
    for step in spec.steps:
        if step.id in step_ids:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=f"duplicate step id {step.id!r}",
                )
            )
        step_ids.add(step.id)
        if step.index in seen_indexes:
            failures.append(
                GateFailure(
                    code="INCOMPLETE_STEP",
                    detail=f"step {step.id!r} reuses index {step.index} — order ambiguous.",
                )
            )
        seen_indexes.add(step.index)
        if not step.action.strip():
            failures.append(
                GateFailure(
                    code="INCOMPLETE_STEP",
                    detail=f"step {step.id!r} has no action.",
                )
            )
        if not step.check.strip():
            failures.append(
                GateFailure(
                    code="INCOMPLETE_STEP",
                    detail=f"step {step.id!r} has no check — unverifiable for the human.",
                )
            )
        for bid in step.uses:
            if bid not in bom_ids:
                failures.append(
                    GateFailure(
                        code="DANGLING_REFERENCE",
                        detail=f"step {step.id!r} uses unknown BOM item {bid!r}",
                    )
                )
        for qid in step.quantity_refs:
            if qid not in quantities:
                failures.append(
                    GateFailure(
                        code="DANGLING_REFERENCE",
                        detail=f"step {step.id!r} references unknown quantity {qid!r}",
                    )
                )
        if step.torque_quantity_id is not None and step.torque_quantity_id not in quantities:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=(
                        f"step {step.id!r} torque references unknown quantity "
                        f"{step.torque_quantity_id!r}"
                    ),
                )
            )

    available: set[str] = set(bom_ids)
    for step in sorted(spec.steps, key=lambda s: s.index):
        for inp in step.inputs:
            if inp not in available:
                failures.append(
                    GateFailure(
                        code="UNBUILDABLE_ORDER",
                        detail=(
                            f"step {step.id!r} needs input {inp!r}, which is neither a "
                            "BOM item nor produced by an earlier step."
                        ),
                    )
                )
        for out in step.outputs:
            if out in available:
                failures.append(
                    GateFailure(
                        code="UNBUILDABLE_ORDER",
                        detail=f"step {step.id!r} redefines artifact {out!r}.",
                    )
                )
            available.add(out)

    # --- Maß: C-12/C-13 -----------------------------------------------------------
    for q in quantities.values():
        if not q.unit.strip():
            failures.append(
                GateFailure(
                    code="UNIT_MISMATCH",
                    detail=f"quantity {q.id!r} ({q.name!r}) has no unit ('1' = dimensionless).",
                )
            )

    # --- Maß: C-13 constraints over arithmetic EXPRESSIONS ------------------------
    # left/right are arithmetic expressions over quantity_ids (a bare id is the
    # trivial case — fully backward compatible). This lets a spec declare bounds
    # like "wall thickness >= 0.1 * width" or "q_t > 0" (plausibility). Every
    # referenced id must resolve (C-8), both sides must be dimensionally
    # comparable (C-12/C-15, with a literal side being dimension-agnostic), and
    # the comparison must hold numerically (C-13).
    value_bindings = {q.id: float(q.value) for q in quantities.values()}
    unc_bindings = {
        q.id: float(q.uncertainty)
        for q in quantities.values()
        if q.uncertainty is not None
    }

    for constraint in spec.constraints:
        if constraint.kind not in CONSTRAINT_KINDS:
            failures.append(
                GateFailure(
                    code="CONSTRAINT_VIOLATION",
                    detail=f"constraint {constraint.id!r} has unknown kind {constraint.kind!r}.",
                )
            )
            continue

        # resolve referenced ids in both expressions (C-8)
        try:
            refs = referenced_names(constraint.left) | referenced_names(constraint.right)
        except FormulaError as exc:
            failures.append(
                GateFailure(
                    code="DANGLING_REFERENCE",
                    detail=f"constraint {constraint.id!r} has an unparseable expression: {exc}",
                )
            )
            continue
        missing = sorted(r for r in refs if r not in quantities)
        if missing:
            for r in missing:
                failures.append(
                    GateFailure(
                        code="DANGLING_REFERENCE",
                        detail=f"constraint {constraint.id!r} references unknown quantity {r!r}",
                    )
                )
            continue

        # dimensional comparability (C-12/C-15) with a literal-side exception
        ref_dims = {r: _dim_of_unit(quantities[r].unit) for r in refs}
        if any(d is None for d in ref_dims.values()):
            failures.append(
                GateFailure(
                    code="UNIT_MISMATCH",
                    detail=f"constraint {constraint.id!r} references a quantity with an unparseable unit.",
                )
            )
            continue
        # scale-mixing guard: same dimension must use one unit string (no m vs cm)
        by_dim: dict[Dimension, set[str]] = {}
        for r in refs:
            by_dim.setdefault(ref_dims[r], set()).add(quantities[r].unit.strip())  # type: ignore[arg-type]
        mixed = [units for units in by_dim.values() if len(units) > 1]
        if mixed:
            failures.append(
                GateFailure(
                    code="UNIT_MISMATCH",
                    detail=(
                        f"constraint {constraint.id!r} mixes different units of the same "
                        f"dimension ({sorted(next(iter(mixed)))}) — convert first."
                    ),
                )
            )
            continue

        left_literal = is_numeric_literal(constraint.left)
        right_literal = is_numeric_literal(constraint.right)
        try:
            left_dim = formula_dimension(constraint.left, ref_dims)  # type: ignore[arg-type]
            right_dim = formula_dimension(constraint.right, ref_dims)  # type: ignore[arg-type]
        except UnitError as exc:
            failures.append(
                GateFailure(
                    code="DIMENSION_MISMATCH",
                    detail=f"constraint {constraint.id!r}: {exc}",
                )
            )
            continue
        if not (left_literal or right_literal) and left_dim != right_dim:
            failures.append(
                GateFailure(
                    code="UNIT_MISMATCH",
                    detail=(
                        f"constraint {constraint.id!r} compares {left_dim.render()} with "
                        f"{right_dim.render()} — dimensions must match."
                    ),
                )
            )
            continue

        # numeric evaluation (C-13). When a side references quantities that carry
        # an uncertainty, the comparison is checked at the GUM-EXPANDED worst-case
        # bound (k=2, ~95 %), not just at the point value — so a declared
        # uncertainty actually GATES the design. With no uncertainty every U is 0
        # and this reduces exactly to the point comparison (fully backward
        # compatible). The bound is taken in the adverse direction per kind.
        try:
            lv = evaluate_formula(constraint.left, value_bindings)
            rv = evaluate_formula(constraint.right, value_bindings)
            u_left = combine_standard_uncertainty(
                constraint.left,
                {r: value_bindings[r] for r in referenced_names(constraint.left)},
                unc_bindings,
            )
            u_right = combine_standard_uncertainty(
                constraint.right,
                {r: value_bindings[r] for r in referenced_names(constraint.right)},
                unc_bindings,
            )
        except FormulaError as exc:
            failures.append(
                GateFailure(
                    code="CONSTRAINT_VIOLATION",
                    detail=f"constraint {constraint.id!r} could not be evaluated: {exc}",
                )
            )
            continue
        ul, ur = 2.0 * u_left, 2.0 * u_right          # expanded (k=2 ≈ 95 %)
        holds = {
            "le": (lv + ul) <= (rv - ur),
            "lt": (lv + ul) < (rv - ur),
            "ge": (lv - ul) >= (rv + ur),
            "gt": (lv - ul) > (rv + ur),
            "eq": within_tolerance(lv, rv, tolerance=derivation_tolerance),
        }[constraint.kind]
        if not holds:
            bound = ""
            if ul or ur:
                bound = (
                    f" at the 95% bound (U_left={ul:g}, U_right={ur:g}); "
                    f"point values were {lv:g} {constraint.kind} {rv:g}"
                )
            failures.append(
                GateFailure(
                    code="CONSTRAINT_VIOLATION",
                    detail=(
                        f"constraint {constraint.id!r} violated: ({constraint.left})="
                        f"{lv} {constraint.kind} ({constraint.right})={rv}{bound} "
                        f"({constraint.reason})"
                    ),
                )
            )

    # --- Maß: C-15 dimensional homogeneity of derivations -------------------------
    # Independent of the numeric recompute (C-6): a formula can recompute to the
    # right NUMBER yet be dimensional nonsense (kg + mm), or an area declared as a
    # length. Dimensional analysis is "a first check on the correctness of an
    # equation" (Kennedy 2009); it guards the Mars-Climate-Orbiter failure class.
    # (_dim_of_unit is defined once near the top of gate_gamma and shared here.)
    for q in quantities.values():
        if q.origin is not ValueOrigin.DERIVED or q.derivation is None:
            continue
        declared = _dim_of_unit(q.unit)
        if declared is None:
            failures.append(
                GateFailure(
                    code="DIMENSION_MISMATCH",
                    detail=f"DERIVED quantity {q.id!r} has an unparseable unit {q.unit!r}.",
                )
            )
            continue
        input_dims: dict[str, Dimension] = {}
        missing_input = False
        for iid in q.derivation.inputs:
            src = quantities.get(iid)
            if src is None:
                missing_input = True  # DANGLING_REFERENCE handled elsewhere
                break
            idim = _dim_of_unit(src.unit)
            if idim is None:
                missing_input = True
                break
            input_dims[iid] = idim
        if missing_input:
            continue
        try:
            computed = formula_dimension(q.derivation.formula, input_dims)
        except UnitError as exc:
            failures.append(
                GateFailure(
                    code="DIMENSION_MISMATCH",
                    detail=f"DERIVED quantity {q.id!r}: {exc}",
                )
            )
            continue
        if computed != declared:
            failures.append(
                GateFailure(
                    code="DIMENSION_MISMATCH",
                    detail=(
                        f"DERIVED quantity {q.id!r}: formula yields "
                        f"{computed.render()} but unit {q.unit!r} is "
                        f"{declared.render()}."
                    ),
                )
            )

    # --- Cross-claim consistency: C-17 over measurand groups ----------------------
    # Two quantities tagged with the same `measurand` claim to measure the SAME
    # physical quantity, so they must agree: same dimension AND the same value
    # after unit conversion. This deterministically catches a contradiction
    # between two accepted, claim-grounded facts — e.g. one grounding claim says
    # the strip runs at 12 V, another (cited elsewhere) says 24 V. The LINK is
    # declared (the measurand tag, made explicit by the architect), the CONFLICT
    # is pure arithmetic + dimensions — no language understanding, no false
    # positive (a conflict is only raised when the values are provably unequal).
    measurand_groups: dict[str, list[Quantity]] = {}
    for q in quantities.values():
        if q.measurand and q.measurand.strip():
            measurand_groups.setdefault(q.measurand.strip(), []).append(q)
    for key, members in sorted(measurand_groups.items()):
        if len(members) < 2:
            continue
        # (a) dimension agreement — measuring one quantity in incompatible
        #     dimensions (V vs mm) is itself a contradiction.
        dims = {m.id: _dim_of_unit(m.unit) for m in members}
        if any(d is None for d in dims.values()):
            failures.append(
                GateFailure(
                    code="CROSS_CLAIM_CONFLICT",
                    detail=(
                        f"measurand {key!r} references a quantity with an "
                        "unparseable unit — cannot prove consistency."
                    ),
                )
            )
            continue
        if len({d for d in dims.values()}) > 1:
            shown = ", ".join(
                f"{m.id}={(d.render() if d else '?')}"
                for m, d in ((m, dims[m.id]) for m in members)
            )
            failures.append(
                GateFailure(
                    code="CROSS_CLAIM_CONFLICT",
                    detail=(
                        f"measurand {key!r} is measured in incompatible dimensions "
                        f"({shown}) — these claim-grounded facts contradict."
                    ),
                )
            )
            continue
        # (b) value agreement after unit conversion to the SI base of the shared
        #     dimension. Unknown/opaque units (no sound scale) fall back to a raw
        #     compare only when the unit strings are identical — otherwise GENESIS
        #     abstains rather than risk a false positive.
        normalized: dict[str, float] = {}
        scale_unknown = False
        for m in members:
            try:
                s = unit_scale(m.unit)
            except UnitError:
                s = None
            if s is None:
                scale_unknown = True
                break
            normalized[m.id] = float(m.value) * s
        if scale_unknown:
            if len({m.unit.strip() for m in members}) != 1:
                continue  # cannot normalize across differing opaque units — abstain
            normalized = {m.id: float(m.value) for m in members}
        ref = members[0]
        ref_val = normalized[ref.id]
        for m in members[1:]:
            if not within_tolerance(ref_val, normalized[m.id], tolerance=derivation_tolerance):
                failures.append(
                    GateFailure(
                        code="CROSS_CLAIM_CONFLICT",
                        detail=(
                            f"measurand {key!r}: {m.id!r} = {m.value:g} {m.unit} "
                            f"contradicts {ref.id!r} = {ref.value:g} {ref.unit} — two "
                            "claim-grounded values for the same quantity disagree."
                        ),
                    )
                )

    # --- Unsicherheit: C-18 GUM propagation recompute -----------------------------
    # A DERIVED quantity that declares an `uncertainty` must have it INDEPENDENTLY
    # recomputable from its inputs' uncertainties by the GUM law of propagation
    # (uncertainty.py) — the exact "code computes, gate recomputes" discipline of
    # C-6, now applied to the uncertainty. An input without a declared uncertainty
    # contributes zero (treated as exact). Skipped silently when the DERIVED value
    # declares no uncertainty (opt-in; no behaviour change for exact specs).
    for q in quantities.values():
        if (
            q.origin is not ValueOrigin.DERIVED
            or q.derivation is None
            or q.uncertainty is None
        ):
            continue
        input_values: dict[str, float] = {}
        input_uncs: dict[str, float] = {}
        resolvable = True
        for iid in q.derivation.inputs:
            src = quantities.get(iid)
            if src is None:
                resolvable = False  # DANGLING_REFERENCE already flagged elsewhere
                break
            input_values[iid] = float(src.value)
            if src.uncertainty is not None:
                input_uncs[iid] = float(src.uncertainty)
        if not resolvable:
            continue
        try:
            recomputed = combine_standard_uncertainty(
                q.derivation.formula, input_values, input_uncs
            )
        except FormulaError:
            continue  # the value recompute (C-6) already reports a broken formula
        if not within_tolerance(float(q.uncertainty), recomputed, tolerance=1e-6):
            failures.append(
                GateFailure(
                    code="BROKEN_UNCERTAINTY",
                    detail=(
                        f"DERIVED quantity {q.id!r} declares u={q.uncertainty:g} but GUM "
                        f"propagation recomputes u={recomputed:g} from its inputs "
                        f"(formula {q.derivation.formula!r})."
                    ),
                )
            )

    # --- β-Kette: C-14 anchoring ----------------------------------------------------
    asserts_content = bool(spec.components or spec.steps)
    if asserts_content:
        if spec.approach_id is None:
            failures.append(
                GateFailure(
                    code="SPEC_NOT_ANCHORED",
                    detail=(
                        "specification asserts content but is not anchored in any "
                        "approach of this run (β chain broken)."
                    ),
                )
            )
        else:
            anchor = next(
                (a for a in state.approaches if a.id == spec.approach_id), None
            )
            if anchor is None:
                failures.append(
                    GateFailure(
                        code="SPEC_NOT_ANCHORED",
                        detail=(
                            f"specification anchored in unknown approach "
                            f"{spec.approach_id!r}."
                        ),
                    )
                )
            else:
                if not anchor.grounding:
                    failures.append(
                        GateFailure(
                            code="SPEC_NOT_ANCHORED",
                            detail=f"anchor approach {anchor.name!r} has no grounding claim.",
                        )
                    )
                for cid in anchor.grounding:
                    claim = claims_by_id.get(cid)
                    if claim is None:
                        failures.append(
                            GateFailure(
                                code="SPEC_NOT_ANCHORED",
                                detail=(
                                    f"anchor approach {anchor.name!r} grounded in unknown "
                                    f"claim {cid!r}."
                                ),
                                claim_id=cid,
                            )
                        )
                        continue
                    if (
                        claim.status is not ClaimStatus.VERIFIED
                        or claim.confidence < confidence_threshold
                    ):
                        failures.append(
                            GateFailure(
                                code="SPEC_NOT_ANCHORED",
                                detail=(
                                    f"anchor approach {anchor.name!r} grounded in "
                                    f"non-verified/under-confident claim: {claim.text!r}"
                                ),
                                claim_id=cid,
                            )
                        )
                    failures.extend(
                        claim_soundness_failures(
                            claim,
                            confidence_threshold=confidence_threshold,
                            flagged=flagged,
                        )
                    )

    # --- Ort: site requirements (declared, claim-informed, resolvable) -----------
    if spec.site is not None:
        if spec.site.available_space is not None:
            for axis, qid in zip(("x", "y", "z"), spec.site.available_space):
                if qid not in quantities:
                    failures.append(
                        GateFailure(
                            code="DANGLING_REFERENCE",
                            detail=(
                                f"site available_space {axis} references unknown quantity "
                                f"{qid!r}"
                            ),
                        )
                    )
        for d in spec.site.requirements:
            if not d.choice.strip() or not d.rationale.strip():
                failures.append(
                    GateFailure(
                        code="UNDECLARED_DECISION",
                        detail=f"site requirement {d.id!r} ({d.title!r}) lacks choice or rationale.",
                    )
                )
            for cid in d.informed_by:
                check_claim_ref(cid, f"site requirement {d.id!r}")

    return GateResult(gate="gamma", passed=not failures, failures=failures)


# --- GATE δ -------------------------------------------------------------------

def _walk_geometry_delta(
    node: GeometryNode,
    quantities: dict[str, Quantity],
    component_name: str,
    failures: list[GateFailure],
) -> None:
    """Recurse a CSG tree, flagging only PROVABLY dead/empty operations (D-2/D-3).

    Soundness: a flag is raised only when bounding boxes are disjoint, which
    means the solids provably do not overlap — never a false positive
    (PHASE_DELTA.md §0). Overlapping boxes claim nothing.
    """
    if node.kind == "difference" and node.children:
        body = aabb_of(node.children[0], quantities)
        for tool in node.children[1:]:
            if not overlaps(body, aabb_of(tool, quantities)):
                failures.append(
                    GateFailure(
                        code="DEAD_OPERATION",
                        detail=(
                            f"component {component_name!r}: a difference subtracts a "
                            f"{tool.kind!r} whose bounding box does not intersect the "
                            "body — it provably removes nothing (e.g. a hole that "
                            "misses the part)."
                        ),
                    )
                )
    if node.kind == "intersection" and len(node.children) >= 2:
        boxes = [aabb_of(c, quantities) for c in node.children]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                if not overlaps(boxes[i], boxes[j]):
                    failures.append(
                        GateFailure(
                            code="EMPTY_INTERSECTION",
                            detail=(
                                f"component {component_name!r}: an intersection combines "
                                f"a {node.children[i].kind!r} and a {node.children[j].kind!r} "
                                "whose bounding boxes are disjoint — the result is "
                                "provably empty."
                            ),
                        )
                    )
    for child in node.children:
        _walk_geometry_delta(child, quantities, component_name, failures)


def gate_delta(state: RunState) -> GateResult:
    """GATE δ — deterministic geometric validation of a γ specification.

    Validates the CSG geometry *before any real effort*, claiming only what
    follows with certainty from axis-aligned bounding boxes (PHASE_DELTA.md §4):

      D-1 DEGENERATE_GEOMETRY   a component's envelope has a non-positive axis.
      D-2 EMPTY_INTERSECTION    an intersection of provably non-overlapping parts.
      D-3 DEAD_OPERATION        a difference whose tool provably removes nothing.
      D-4 EMPTY_GEOMETRY_TREE   a fabricated component reduces to an empty region.

    Honest asymmetry (the whole point, §0): a PASS means "no provably broken
    geometric defect", NOT "physically valid / manufacturable / strong enough" —
    δ never claims a physics judgement. A FAIL means "definitely broken". δ never
    raises a false positive: it only flags disjoint bounding boxes.
    """
    spec = state.specification
    if spec is None:
        return GateResult(
            gate="delta",
            passed=False,
            failures=[GateFailure(code="NO_SPECIFICATION", detail="No specification to validate.")],
        )

    quantities = {q.id: q for q in spec.quantities}
    failures: list[GateFailure] = []

    for comp in spec.components:
        if comp.geometry is None:
            continue
        try:
            envelope = aabb_of(comp.geometry, quantities)
        except GeometryError as exc:
            failures.append(
                GateFailure(
                    code="EMPTY_GEOMETRY_TREE",
                    detail=f"component {comp.name!r}: geometry could not be bounded: {exc}",
                )
            )
            continue
        if envelope.empty:
            failures.append(
                GateFailure(
                    code="EMPTY_GEOMETRY_TREE",
                    detail=f"component {comp.name!r}: geometry reduces to a provably empty region.",
                )
            )
        elif envelope.is_degenerate():
            ex, ey, ez = envelope.extent
            failures.append(
                GateFailure(
                    code="DEGENERATE_GEOMETRY",
                    detail=(
                        f"component {comp.name!r}: envelope has a non-positive axis "
                        f"(extent {ex:g} x {ey:g} x {ez:g}) — no volume to build."
                    ),
                )
            )
        _walk_geometry_delta(comp.geometry, quantities, comp.name, failures)

    # site fit: each component's bounding box must fit the declared available space
    # (axis-aligned, any orientation → compare sorted dimension triples).
    if spec.site is not None and spec.site.available_space is not None:
        space_ids = spec.site.available_space
        if all(qid in quantities for qid in space_ids):
            space = sorted(float(quantities[qid].value) for qid in space_ids)
            for comp in spec.components:
                if comp.geometry is None:
                    continue
                try:
                    env = sorted(aabb_of(comp.geometry, quantities).extent)
                except GeometryError:
                    continue
                if any(e > s + 1e-9 for e, s in zip(env, space)):
                    failures.append(
                        GateFailure(
                            code="SITE_SPACE_EXCEEDED",
                            detail=(
                                f"component {comp.name!r} bounding box {env} does not fit the "
                                f"available space {space} (any orientation)."
                            ),
                        )
                    )

    return GateResult(gate="delta", passed=not failures, failures=failures)


def gate_erc(state: RunState) -> GateResult:
    """GATE ERC — deterministic Electrical Rule Check of a γ specification.

    The electronics analogue of GATE δ: it validates the netlist's CONNECTIVITY
    with certainty, no simulation (PHASE_DELTA.md §13). Pure logic — no SPICE, no
    external engine, fully offline:

      E-1 DANGLING_PIN_REF    a net connects a pin that was never declared.
      E-2 DANGLING_PART       a pin belongs to a part not in the BOM.
      E-3 DUPLICATE_PIN       the same part.pin is declared twice.
      E-4 FLOATING_NET        a net wires fewer than two pins (connects nothing).
      E-5 UNCONNECTED_PIN     a declared pin appears in no net.
      E-6 PIN_MULTIPLE_NETS   a pin appears in more than one net (one node only).
      E-7 POWER_CONFLICT      two POWER_OUT drivers shorted onto one net.
      E-8 UNDRIVEN_INPUT      a net with a POWER_IN load but no POWER_OUT driver.

    Honest asymmetry (like δ): a PASS means "no provably broken connectivity", not
    "the circuit works" (no SPICE / timing / thermal judgement). A FAIL means
    "definitely broken wiring". A spec without a netlist passes trivially — there
    is nothing electrical to validate (the mechanical-only case).
    """
    spec = state.specification
    if spec is None:
        return GateResult(
            gate="erc",
            passed=False,
            failures=[GateFailure(code="NO_SPECIFICATION", detail="No specification to validate.")],
        )
    if spec.netlist is None:
        return GateResult(gate="erc", passed=True, failures=[])

    failures: list[GateFailure] = []
    bom_ids = {b.id for b in spec.bom}

    # declared pins, keyed "part.name"; duplicates are a defect (E-3)
    pin_by_key: dict[str, Pin] = {}
    for pin in spec.netlist.pins:
        key = f"{pin.part}.{pin.name}"
        if key in pin_by_key:
            failures.append(
                GateFailure(code="DUPLICATE_PIN", detail=f"pin {key!r} declared more than once.")
            )
        pin_by_key[key] = pin
        if bom_ids and pin.part not in bom_ids:
            failures.append(
                GateFailure(
                    code="DANGLING_PART",
                    detail=f"pin {key!r} belongs to part {pin.part!r}, which is not in the BOM.",
                )
            )

    # net membership: each pin must appear in exactly one net
    nets_of_pin: dict[str, list[str]] = {}
    net_names: set[str] = set()
    for net in spec.netlist.nets:
        if net.name in net_names:
            failures.append(
                GateFailure(code="DANGLING_PIN_REF", detail=f"duplicate net name {net.name!r}.")
            )
        net_names.add(net.name)
        if len(net.pins) < 2:
            failures.append(
                GateFailure(
                    code="FLOATING_NET",
                    detail=f"net {net.name!r} wires {len(net.pins)} pin(s) — connects nothing.",
                )
            )
        drivers = loads = 0
        for ref in net.pins:
            nets_of_pin.setdefault(ref, []).append(net.name)
            pin = pin_by_key.get(ref)
            if pin is None:
                failures.append(
                    GateFailure(
                        code="DANGLING_PIN_REF",
                        detail=f"net {net.name!r} connects undeclared pin {ref!r}.",
                    )
                )
                continue
            if pin.type is PinType.POWER_OUT:  # type: ignore[attr-defined]
                drivers += 1
            elif pin.type is PinType.POWER_IN:  # type: ignore[attr-defined]
                loads += 1
        if drivers >= 2:
            failures.append(
                GateFailure(
                    code="POWER_CONFLICT",
                    detail=f"net {net.name!r} shorts {drivers} power drivers together.",
                )
            )
        if loads >= 1 and drivers == 0:
            failures.append(
                GateFailure(
                    code="UNDRIVEN_INPUT",
                    detail=f"net {net.name!r} has a power load but no driver.",
                )
            )

    for key in pin_by_key:
        appears = nets_of_pin.get(key, [])
        if not appears:
            failures.append(
                GateFailure(code="UNCONNECTED_PIN", detail=f"declared pin {key!r} is in no net.")
            )
        elif len(appears) > 1:
            failures.append(
                GateFailure(
                    code="PIN_MULTIPLE_NETS",
                    detail=f"pin {key!r} appears in nets {sorted(appears)} — a pin is one node.",
                )
            )

    return GateResult(gate="erc", passed=not failures, failures=failures)


def gate_code(state: RunState) -> GateResult:
    """GATE CODE — validate software deliverables by EXECUTION.

    The strongest deterministic validator in GENESIS: every code artifact in the
    spec is run (source + its check) in an isolated subprocess; the gate passes
    only if every check exits zero. No formula, no model judgement — the machine
    executes and decides (PHASE_DELTA.md §17).

      S-1 UNSUPPORTED_LANGUAGE  the artifact's language has no local runtime here
                                (only Python runs deterministically) — reported,
                                not faked.
      S-2 CODE_TIMEOUT          the check exceeded the wall-clock limit.
      S-3 CODE_CHECK_FAILED     the process exited non-zero (failed assertion,
                                syntax error, exception) — the deliverable is broken.

    A spec with no code artifacts passes trivially. Honest asymmetry: a PASS means
    "compiles and the declared checks pass" — necessary and, for the checked
    behaviour, sufficient; it does not prove the checks themselves are complete.
    """
    import subprocess

    spec = state.specification
    if spec is None:
        return GateResult(
            gate="code",
            passed=False,
            failures=[GateFailure(code="NO_SPECIFICATION", detail="No specification to validate.")],
        )

    failures: list[GateFailure] = []
    for art in spec.code_artifacts:
        if art.language not in SUPPORTED_LANGUAGES:
            failures.append(
                GateFailure(
                    code="UNSUPPORTED_LANGUAGE",
                    detail=(
                        f"code artifact {art.id!r} is {art.language!r}; only "
                        f"{list(SUPPORTED_LANGUAGES)} run deterministically here."
                    ),
                )
            )
            continue
        try:
            passed, output = run_python_artifact(art.source, art.check)
        except subprocess.TimeoutExpired:
            failures.append(
                GateFailure(
                    code="CODE_TIMEOUT",
                    detail=f"code artifact {art.id!r} ({art.name!r}) exceeded the time limit.",
                )
            )
            continue
        if not passed:
            tail = output.strip().splitlines()[-1] if output.strip() else "no output"
            failures.append(
                GateFailure(
                    code="CODE_CHECK_FAILED",
                    detail=f"code artifact {art.id!r} ({art.name!r}) failed its check: {tail}",
                )
            )

    return GateResult(gate="code", passed=not failures, failures=failures)


#: Minimum independent replicates for a quantitative claim. n >= 3 is the common
#: floor for elementary statistics (a mean + a spread estimate); fewer cannot
#: support a reproducible quantitative conclusion. Declared, documented threshold.
MIN_REPLICATES = 3


def gate_protocol(state: RunState) -> GateResult:
    """GATE PROTOCOL — deterministic reproducibility-design check for a wet-lab /
    field protocol (the reproducibility arc for general protocols, e.g. mechanical/energy storage; PHASE_DELTA.md §19 — no biology).

    A protocol that measures a quantitative outcome but has no control or too few
    replicates is the root of the reproducibility crisis. This checks the design
    deterministically (parameter SAFETY LIMITS and unit correctness reuse the
    existing constraint machinery, C-13 / C-15 — no duplication):

      P-1 MEASURE_WITHOUT_CONTROL   a measured outcome with no named control group.
      P-2 CONTROL_NOT_IN_GROUPS     the named control is not among the groups.
      P-3 TOO_FEW_GROUPS            a measured outcome with fewer than two groups.
      P-4 INSUFFICIENT_REPLICATES   fewer than MIN_REPLICATES replicates.

    A spec with no experiment design passes trivially (a non-experimental build).
    Honest asymmetry: a PASS means "the design can in principle support a
    reproducible quantitative conclusion", not that the experiment will succeed.
    """
    spec = state.specification
    if spec is None:
        return GateResult(
            gate="protocol",
            passed=False,
            failures=[GateFailure(code="NO_SPECIFICATION", detail="No specification to validate.")],
        )
    exp = spec.experiment
    if exp is None:
        return GateResult(gate="protocol", passed=True, failures=[])

    failures: list[GateFailure] = []
    if exp.measured.strip():
        if exp.control is None:
            failures.append(
                GateFailure(
                    code="MEASURE_WITHOUT_CONTROL",
                    detail=(
                        f"the protocol measures {exp.measured!r} but declares no control "
                        "group — no baseline to attribute the effect to."
                    ),
                )
            )
        elif exp.control not in exp.groups:
            failures.append(
                GateFailure(
                    code="CONTROL_NOT_IN_GROUPS",
                    detail=f"control {exp.control!r} is not among the groups {exp.groups}.",
                )
            )
        if len(set(exp.groups)) < 2:
            failures.append(
                GateFailure(
                    code="TOO_FEW_GROUPS",
                    detail=(
                        f"a measured outcome needs >= 2 distinct groups (treatment + "
                        f"control), got {exp.groups}."
                    ),
                )
            )
    if exp.replicates < MIN_REPLICATES:
        failures.append(
            GateFailure(
                code="INSUFFICIENT_REPLICATES",
                detail=(
                    f"{exp.replicates} replicate(s) < the minimum {MIN_REPLICATES} for a "
                    "reproducible quantitative conclusion."
                ),
            )
        )

    return GateResult(gate="protocol", passed=not failures, failures=failures)


def geometry_envelope(state: RunState) -> dict[str, tuple[float, float, float]]:
    """Per-component bounding-box extents (x, y, z) — the δ validation surface
    shown to the human ('does it fit my build volume?'). Skips components without
    geometry and any that cannot be bounded (those are δ failures, not envelopes).
    """
    spec = state.specification
    out: dict[str, tuple[float, float, float]] = {}
    if spec is None:
        return out
    quantities = {q.id: q for q in spec.quantities}
    for comp in spec.components:
        if comp.geometry is None:
            continue
        try:
            box = aabb_of(comp.geometry, quantities)
        except GeometryError:
            continue
        if not box.empty:
            out[comp.id] = box.extent
    return out


def dream_to_hammer_gate(hammer: Any) -> GateResult:
    """GATE dream-to-hammer — LUMENCRUCIBLE Ω v1 (HORIZON entry for dreams).

    A raw dream is turned into a minimal actionable first "hammer"
    (smallest falsifiable teststand/experiment step with CAD + gate target).

    This gate is the deterministic backstop (LLM-free) that the produced
    LumenHammer is well-formed before being treated as a HORIZON ignition.

    P-1 HAMMER_MISSING_FIELD    — required provenance + action fields present and non-empty
    P-2 UNKNOWN_HAMMER_GATE     — gate_to_pass must name a known HORIZON gate
    P-3 VAGUE_HAMMER            — experiment_name too short/empty

    A hammer that passes is ready for OmegaCertificate, Claim, and WORK_QUEUE self-ascent.
    Pure, deterministic, unit-testable. Mirrors the spirit of gate_phi / gate_chi.
    """
    from typing import Any as _Any  # local to avoid top-level issues

    failures: list[GateFailure] = []

    # Robust access (dataclass or dict)
    if isinstance(hammer, dict):
        h = hammer
    else:
        h = getattr(hammer, "__dict__", {}) or {}
        # fallback to attributes
        if not h:
            h = {k: getattr(hammer, k, None) for k in ("experiment_name", "description", "next_step", "gate_to_pass", "quelle", "frontier_snapshot")}

    def _get(k: str):
        return h.get(k) if isinstance(h, dict) else getattr(hammer, k, None)

    # P-1 + P-3 core fields
    for k in ("experiment_name", "description", "next_step", "gate_to_pass", "quelle"):
        v = _get(k)
        if not v or (isinstance(v, str) and len(v.strip()) < 3):
            failures.append(
                GateFailure(code="HAMMER_MISSING_FIELD", detail=f"hammer missing/empty {k}")
            )

    gtp = _get("gate_to_pass")
    known_gates = {
        "gate_delta_plus", "gate_delta_plus_coverage",
        "gate_omega", "gate_epsilon", "gate_zeta", "gate_gamma_plus",
        "gate_phi", "gate_chi", "gate_alpha", "gate_beta", "gate_delta",
        "lumencrucible_pre_gate"
    }
    if gtp and isinstance(gtp, str) and gtp not in known_gates:
        failures.append(
            GateFailure(code="UNKNOWN_HAMMER_GATE", detail=f"gate_to_pass {gtp!r} not recognized HORIZON gate")
        )

    # frontier optional but should be present
    fs = _get("frontier_snapshot")
    if fs is None:
        # not fatal for early dreams
        pass

    return GateResult(
        gate="dream-to-hammer",
        passed=not failures,
        failures=failures,
    )
