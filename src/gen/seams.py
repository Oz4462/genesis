"""Phase epsilon — verified seams between engineering domains.

Each GENESIS domain can be locally honest and still fail at the interface: electrical
power becomes thermal heat, thermal expansion consumes mechanical clearance, firmware
limits must respect electrical current budgets, and cost must match the priced BOM.

This module makes those interfaces explicit. A ``DomainSeam`` is not prose; it is a
typed relation over specification quantities (or a cost roll-up relation) that the gate
recomputes deterministically. No model judgement, no hidden cross-domain assumption.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .core.errors import FormulaError, UnitError
from .core.interfaces import GateFailure, GateResult
from .core.state import (
    BomDomain,
    BomRole,
    DomainSeam,
    Quantity,
    SeamCertificate,
    SeamDomain,
    SeamRelation,
    Specification,
)
from .costing import bom_cost
from .verification.derivation import (
    DEFAULT_TOLERANCE,
    evaluate_formula,
    referenced_names,
)
from .verification.units import (
    DIMENSIONLESS,
    Dimension,
    formula_dimension,
    parse_unit,
    unit_scale,
)


_CHAIN: tuple[SeamDomain, ...] = (
    SeamDomain.MECHANICAL,
    SeamDomain.THERMAL,
    SeamDomain.ELECTRICAL,
    SeamDomain.FIRMWARE,
)


@dataclass(frozen=True)
class EvaluatedExpression:
    """A seam expression evaluated in SI-scaled units plus its dimension."""

    value: float
    dimension: Dimension


def _pair(a: SeamDomain, b: SeamDomain) -> tuple[SeamDomain, SeamDomain]:
    return tuple(sorted((a, b), key=lambda domain: domain.value))  # type: ignore[return-value]


def _quantity_map(spec: Specification) -> dict[str, Quantity]:
    return {q.id: q for q in spec.quantities}


def _looks_thermal(q: Quantity) -> bool:
    text = " ".join(part for part in (q.id, q.name, q.measurand or "")).lower()
    markers = (
        "thermal",
        "temperature",
        "temp",
        "heat",
        "ambient",
        "conduct",
        "dissipat",
        "service_limit",
    )
    return q.unit in {"K", "deg"} or any(marker in text for marker in markers)


def domains_present(spec: Specification) -> set[SeamDomain]:
    """Detect which domains are present enough for epsilon seam coverage."""
    present: set[SeamDomain] = set()
    if spec.components or any(item.domain is BomDomain.MECHANICAL for item in spec.bom):
        present.add(SeamDomain.MECHANICAL)
    # topology / SIMP density field implies MECH structure (richer generative design).
    # Scan quantity + component labels only (no str(spec) — avoids accidental matches
    # on unrelated text). Fixed NameError from prior draft that referenced unbound `c`.
    qty_text = " ".join(
        f"{getattr(q, 'id', '') or ''} {getattr(q, 'name', '') or ''} "
        f"{getattr(q, 'measurand', '') or ''}"
        for q in (spec.quantities or [])
    )
    comp_text = " ".join(
        f"{getattr(comp, 'name', '') or ''} {getattr(comp, 'role', '') or ''}"
        for comp in (spec.components or [])
    )
    text_all = f"{qty_text} {comp_text}".lower()
    if any(k in text_all for k in ("topology", "density", "simp", "vorschlag", "dichtefeld")):
        present.add(SeamDomain.MECHANICAL)
    if any(_looks_thermal(q) for q in spec.quantities):
        present.add(SeamDomain.THERMAL)
    if spec.netlist is not None or any(
        item.domain is BomDomain.ELECTRONIC for item in spec.bom
    ):
        present.add(SeamDomain.ELECTRICAL)
    if spec.code_artifacts:
        present.add(SeamDomain.FIRMWARE)
    if any(item.role in (BomRole.PART, BomRole.MATERIAL) for item in spec.bom):
        present.add(SeamDomain.COST)
    return present


def required_seam_pairs(spec: Specification) -> list[tuple[SeamDomain, SeamDomain]]:
    """Adjacent chain pairs whose domains are both present and therefore need a seam."""
    present = domains_present(spec)
    required: list[tuple[SeamDomain, SeamDomain]] = []
    for left, right in zip(_CHAIN, _CHAIN[1:], strict=False):
        if left in present and right in present:
            required.append(_pair(left, right))
    return required


def cost_rollup_required(spec: Specification) -> bool:
    """True when a spec has buyable items whose cost must be coupled to BOM pricing."""
    return any(item.role in (BomRole.PART, BomRole.MATERIAL) for item in spec.bom)


def evaluate_seam_expression(spec: Specification, expr: str) -> EvaluatedExpression:
    """Evaluate a seam expression with unit scaling and dimensional proof."""
    quantities = _quantity_map(spec)
    names = referenced_names(expr)

    values: dict[str, float] = {}
    dims: dict[str, Dimension] = {}
    for name in names:
        q = quantities.get(name)
        if q is None:
            raise FormulaError(expr, f"unknown quantity {name!r}")
        scale = unit_scale(q.unit)
        if scale is None:
            raise UnitError(f"quantity {name!r} has opaque unit {q.unit!r}")
        values[name] = q.value * scale
        dims[name] = parse_unit(q.unit)

    dimension = formula_dimension(expr, dims) if names else DIMENSIONLESS
    value = evaluate_formula(expr, values)
    return EvaluatedExpression(value=value, dimension=dimension)


def _relation_holds(
    left: float,
    right: float,
    relation: SeamRelation,
    *,
    tolerance: float,
) -> bool:
    if relation is SeamRelation.EQ:
        return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)
    if relation is SeamRelation.LE:
        return left <= right + tolerance
    if relation is SeamRelation.GE:
        return left + tolerance >= right
    raise ValueError(f"unsupported seam relation {relation.value!r}")


def _compare_seam(
    spec: Specification,
    seam: DomainSeam,
    *,
    tolerance: float,
) -> list[GateFailure]:
    failures: list[GateFailure] = []
    if seam.relation is SeamRelation.COST_ROLLUP:
        return _check_cost_rollup(spec, seam, tolerance=tolerance)
    if SeamDomain.COST in (seam.left_domain, seam.right_domain):
        return [
            GateFailure(
                code="COST_SEAM_REQUIRES_ROLLUP",
                detail=(
                    f"seam {seam.id!r} touches COST but uses {seam.relation.value!r}; "
                    "cost seams must use COST_ROLLUP."
                ),
                claim_id=seam.id,
            )
        ]

    try:
        left = evaluate_seam_expression(spec, seam.left_expr)
        right = evaluate_seam_expression(spec, seam.right_expr)
    except (FormulaError, UnitError) as exc:
        return [
            GateFailure(
                code="SEAM_EXPRESSION_ERROR",
                detail=f"seam {seam.id!r}: {exc}",
                claim_id=seam.id,
            )
        ]

    if left.dimension != right.dimension:
        failures.append(
            GateFailure(
                code="SEAM_DIMENSION_MISMATCH",
                detail=(
                    f"seam {seam.id!r} compares {left.dimension.render()} to "
                    f"{right.dimension.render()}."
                ),
                claim_id=seam.id,
            )
        )
        return failures

    if not _relation_holds(left.value, right.value, seam.relation, tolerance=tolerance):
        failures.append(
            GateFailure(
                code="SEAM_RELATION_VIOLATION",
                detail=(
                    f"seam {seam.id!r}: {seam.left_expr!r}={left.value:g} "
                    f"{seam.relation.value} {seam.right_expr!r}={right.value:g} is false."
                ),
                claim_id=seam.id,
            )
        )
    return failures


def _check_cost_rollup(
    spec: Specification,
    seam: DomainSeam,
    *,
    tolerance: float,
) -> list[GateFailure]:
    if SeamDomain.COST not in (seam.left_domain, seam.right_domain):
        return [
            GateFailure(
                code="COST_ROLLUP_WITHOUT_COST_DOMAIN",
                detail=f"seam {seam.id!r} uses COST_ROLLUP but does not include COST.",
                claim_id=seam.id,
            )
        ]

    quantities = _quantity_map(spec)
    declared = quantities.get(seam.left_expr)
    if declared is None:
        return [
            GateFailure(
                code="COST_TOTAL_UNKNOWN",
                detail=(
                    f"cost seam {seam.id!r} references unknown total quantity "
                    f"{seam.left_expr!r}."
                ),
                claim_id=seam.id,
            )
        ]

    cost = bom_cost(spec)
    if not cost.complete:
        return [
            GateFailure(
                code="COST_INCOMPLETE",
                detail=(
                    f"cost seam {seam.id!r} cannot certify total; unpriced items: "
                    f"{', '.join(cost.unpriced)}."
                ),
                claim_id=seam.id,
            )
        ]

    currency = seam.right_expr.strip()
    subtotal = cost.subtotals.get(currency)
    if subtotal is None:
        return [
            GateFailure(
                code="COST_CURRENCY_MISSING",
                detail=f"cost seam {seam.id!r} has no BOM subtotal for {currency!r}.",
                claim_id=seam.id,
            )
        ]
    if declared.unit != currency:
        return [
            GateFailure(
                code="COST_UNIT_MISMATCH",
                detail=(
                    f"cost seam {seam.id!r}: quantity {declared.id!r} unit "
                    f"{declared.unit!r} is not currency {currency!r}."
                ),
                claim_id=seam.id,
            )
        ]
    if not math.isclose(declared.value, subtotal, rel_tol=tolerance, abs_tol=tolerance):
        return [
            GateFailure(
                code="COST_ROLLUP_MISMATCH",
                detail=(
                    f"cost seam {seam.id!r}: declared {declared.value:g} {currency}, "
                    f"BOM roll-up is {subtotal:g} {currency}."
                ),
                claim_id=seam.id,
            )
        ]
    return []


def build_seam_certificate(
    spec: Specification,
    seams: list[DomainSeam],
    *,
    complete: bool = True,
) -> SeamCertificate:
    """Mechanical builder: attach supplied seams to a spec-run certificate."""
    return SeamCertificate(
        spec_run_id=spec.run_id,
        seams=list(seams),
        complete=complete,
        produced_by="seam_builder",
    )


def gate_epsilon(
    spec: Specification,
    certificate: SeamCertificate,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> GateResult:
    """GATE epsilon — deterministic cross-domain seam verification.

    Passes only when every required adjacent domain pair has at least one declared seam,
    every seam expression is dimensionally valid and satisfies its relation, and cost
    roll-up seams match `bom_cost`. This gate proves coupling, not local domain success;
    local gates (γ, δ, ERC, CODE) remain their own authorities.
    """
    failures: list[GateFailure] = []

    if certificate.spec_run_id != spec.run_id:
        failures.append(
            GateFailure(
                code="SEAM_SPEC_MISMATCH",
                detail=(
                    f"certificate belongs to run {certificate.spec_run_id!r}, "
                    f"not spec run {spec.run_id!r}."
                ),
            )
        )
    if not certificate.complete:
        failures.append(
            GateFailure(
                code="INCOMPLETE_SEAM_CERTIFICATE",
                detail="seam certificate is not marked complete.",
            )
        )

    present = domains_present(spec)
    seen_ids: set[str] = set()
    covered_pairs: set[tuple[SeamDomain, SeamDomain]] = set()
    has_cost_rollup = False

    for seam in certificate.seams:
        if seam.id in seen_ids:
            failures.append(
                GateFailure(
                    code="DUPLICATE_SEAM_ID",
                    detail=f"seam id {seam.id!r} appears more than once.",
                    claim_id=seam.id,
                )
            )
        seen_ids.add(seam.id)

        for domain in (seam.left_domain, seam.right_domain):
            if domain not in present:
                failures.append(
                    GateFailure(
                        code="SEAM_DOMAIN_NOT_PRESENT",
                        detail=f"seam {seam.id!r} references absent domain {domain.value!r}.",
                        claim_id=seam.id,
                    )
                )

        covered_pairs.add(_pair(seam.left_domain, seam.right_domain))
        if seam.relation is SeamRelation.COST_ROLLUP:
            has_cost_rollup = True
        failures.extend(_compare_seam(spec, seam, tolerance=tolerance))

    for required in required_seam_pairs(spec):
        if required not in covered_pairs:
            failures.append(
                GateFailure(
                    code="MISSING_REQUIRED_SEAM",
                    detail=(
                        f"domains {required[0].value!r} and {required[1].value!r} "
                        "are both present but no seam couples them."
                    ),
                )
            )

    if cost_rollup_required(spec) and not has_cost_rollup:
        failures.append(
            GateFailure(
                code="MISSING_COST_ROLLUP",
                detail="spec has buyable BOM items but no COST_ROLLUP seam.",
            )
        )

    return GateResult(gate="epsilon", passed=not failures, failures=failures)


def detect_cross_domain_seams(spec: Specification) -> list[DomainSeam]:
    """Auto-detect richer DomainSeams (cross-domain) from architect spec (post-γ) or assess (after spec).
    Detects from: constraints (left/right as qty exprs + kind for relation) + bom/quantities for COST_ROLLUP.
    Smallest correct: only emits when backing quantities exist in spec (no expression errors from phantom ids).
    Uses existing detectors (domains_present, cost_rollup_required). May return [] for non-cross specs (honest).
    Rationale: "auto from spec/constraints per gap report".
    """
    seams: list[DomainSeam] = []
    if not spec:
        return seams
    qmap = _quantity_map(spec)
    qids = set(qmap.keys())
    present = domains_present(spec)

    # 1. Cost rollup (from bom + existing total-like quantity; matches test _spec + s_cost pattern)
    if cost_rollup_required(spec) and SeamDomain.COST in present:
        for qid in sorted(qids):
            if any(k in qid.lower() for k in ("total", "cost", "preis", "sum")):
                q = qmap[qid]
                if q.unit and q.unit.strip() in ("EUR", "USD", "€", "$", "currency"):
                    # distinct right domain from present (non-COST)
                    right = next(
                        (d for d in present if d != SeamDomain.COST),
                        SeamDomain.MECHANICAL,
                    )
                    seams.append(
                        DomainSeam(
                            id=f"auto_cost_{qid}",
                            left_domain=SeamDomain.COST,
                            right_domain=right,
                            relation=SeamRelation.COST_ROLLUP,
                            left_expr=qid,
                            right_expr=q.unit.strip(),
                            rationale="auto-detected COST_ROLLUP from bom-priced spec total vs bom_cost (from architect spec or assess)",
                        )
                    )
                    break  # one sufficient
    # NOTE: topology/SIMP density is an *intra*-MECHANICAL generative design step,
    # not a cross-domain seam. DomainSeam requires two distinct domains
    # (core/state.py). Topology keywords may still mark MECH present via
    # domains_present(); they must never emit a MECH↔MECH DomainSeam
    # (REWORK 2026-07-11: removed invalid same-domain seam that broke ε E2E).

    # 2. Cross-domain from constraints (explicit relations in γ spec; kind -> relation)
    # Enhanced expr support (Return Gate #4 + harness 5.5 Return Gate discipline):
    # Use referenced_names (already imported) to resolve qids even if left/right are expressions
    # (e.g. "F_max <= sigma_yield"). Falls back to direct match for simple ids. Keeps exprs as-is.
    kind_to_rel = {
        "le": SeamRelation.LE,
        "le=": SeamRelation.LE,
        "ge": SeamRelation.GE,
        "ge=": SeamRelation.GE,
        "eq": SeamRelation.EQ,
        "=": SeamRelation.EQ,
        "==": SeamRelation.EQ,
    }
    for con in spec.constraints or []:
        left = (con.left or "").strip()
        right = (con.right or "").strip()
        if left and right:
            lrefs = referenced_names(left) & qids
            rrefs = referenced_names(right) & qids
            lqid = (
                left if left in qids else (next(iter(lrefs), None) if lrefs else None)
            )
            rqid = (
                right if right in qids else (next(iter(rrefs), None) if rrefs else None)
            )
            if lqid and rqid and lqid in qids and rqid in qids:
                # infer distinct domains (heuristic via names/measurand + _looks_thermal)
                lq = qmap.get(lqid)
                rq = qmap.get(rqid)
                ld = _guess_domain(lq) or SeamDomain.MECHANICAL
                rd = _guess_domain(rq) or SeamDomain.ELECTRICAL
                if ld == rd:
                    # force adjacent if possible
                    rd = next((d for d in present if d != ld), SeamDomain.THERMAL)
                rel = kind_to_rel.get((con.kind or "").strip().lower(), SeamRelation.EQ)
                seams.append(
                    DomainSeam(
                        id=f"auto_con_{con.id or left}",
                        left_domain=ld,
                        right_domain=rd,
                        relation=rel,
                        left_expr=left,
                        right_expr=right,
                        rationale=f"auto cross-domain seam from spec constraint {con.id}: {con.reason or ''} (post-γ architect; expr support via referenced_names per Return Gate)",
                    )
                )

    return seams


def _guess_domain(q: Quantity | None) -> SeamDomain | None:
    """Tiny internal helper (not exported)."""
    if not q:
        return None
    text = " ".join(p for p in (q.id, q.name or "", q.measurand or "")).lower()
    if (
        _looks_thermal(q)
        or "thermal" in text
        or "temp" in text
        or "heat" in text
        or "expansion" in text
    ):
        return SeamDomain.THERMAL
    if any(
        m in text
        for m in (
            "elec",
            "power",
            "current",
            "volt",
            "dissip",
            "electronics",
            "bus",
            "signal",
        )
    ):
        return SeamDomain.ELECTRICAL
    if any(
        m in text
        for m in (
            "mech",
            "clearance",
            "stress",
            "force",
            "mechanical",
            "dim",
            "torque",
            "pressure",
            "load",
        )
    ):
        return SeamDomain.MECHANICAL
    if "fw" in text or "firmware" in text or "code" in text:
        return SeamDomain.FIRMWARE
    if "cost" in text or "bom" in text or "price" in text:
        return SeamDomain.COST
    if any(k in text for k in ("topology", "density", "simp", "vorschlag", "dichtefeld")):
        return SeamDomain.MECHANICAL
    return None


__all__ = [
    "EvaluatedExpression",
    "build_seam_certificate",
    "cost_rollup_required",
    "detect_cross_domain_seams",
    "domains_present",
    "evaluate_seam_expression",
    "gate_epsilon",
    "required_seam_pairs",
]
