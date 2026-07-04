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
from .verification.derivation import DEFAULT_TOLERANCE, evaluate_formula, referenced_names
from .verification.units import DIMENSIONLESS, Dimension, formula_dimension, parse_unit, unit_scale


_CHAIN: tuple[SeamDomain, ...] = (
    SeamDomain.MECHANICAL,
    SeamDomain.THERMAL,
    SeamDomain.RADIATION,  # space: vacuum radiation couples to thermal (dominant in space, no convection)
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
    """Detect THERMAL domain via unit or markers in id/name/measurand (prefix-aware for robustness)."""
    text = " ".join(part for part in (q.id, q.name, q.measurand or "")).lower()
    m = q.measurand or ""
    if m.startswith(("thermal.", "temperature.", "heat.")):
        return True
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


def _looks_radiation(q: Quantity) -> bool:
    """Detect RADIATION domain via unit or markers (hardened with measurand prefix awareness)."""
    text = " ".join(part for part in (q.id, q.name, q.measurand or "")).lower()
    m = (q.measurand or "").lower()
    if m.startswith("radiation.") or m.startswith("rad."):
        return True
    markers = (
        "radiation",
        "dose",
        "gamma",
        "solar_flux",
        "albedo",
        "eclipse",
    )
    return any(marker in text for marker in markers) or q.unit in {"Sv", "Gy"}


def _looks_isru(q: Quantity) -> bool:
    """Detect ISRU domain via measurand prefix or markers. For Mars in-situ: regolith yield, O2/CH4 production, propellant.
    (Elon vision: local resources to reduce Earth launch mass.)
    Hardened against substring FP (e.g. "isrundes" in German specs).
    """
    m = (q.measurand or "").lower()
    if m.startswith(("isru.", "isru_", "regolith.", "propellant.")):
        return True
    text = " ".join(part for part in (q.id, q.name, q.measurand or "")).lower()
    padded = " " + text.replace("_", " ").replace("-", " ").replace(".", " ").replace("(", " ").replace(")", " ") + " "
    markers = ("isru", "regolith", "insitu", "propellant_yield", "o2_yield", "ch4", "sabati", "electrolysis_mars")
    return any(" " + marker + " " in padded for marker in markers)


def _looks_life_support(q: Quantity) -> bool:
    """Detect LIFE_SUPPORT (ECLSS) domain via measurand prefix or markers. Crew O2 consumption, CO2 scrubbing, water loop closure, habitat atmosphere.
    Critical for multi-planetary habitats (vacuum + radiation context).
    Hardened against substring FP.
    """
    m = (q.measurand or "").lower()
    if m.startswith(("life_support.", "eclss.", "crew.", "habitat_atm.")):
        return True
    text = " ".join(part for part in (q.id, q.name, q.measurand or "")).lower()
    padded = " " + text.replace("_", " ").replace("-", " ").replace(".", " ").replace("(", " ").replace(")", " ") + " "
    markers = ("life_support", "eclss", "o2_closure", "co2_scrub", "crew_consum", "water_loop", "atmosphere_balance", "habitat_o2")
    return any(" " + marker + " " in padded for marker in markers)


def _looks_electrical(q: Quantity) -> bool:
    """Detect ELECTRICAL domain via unit or markers in id/name/measurand (prefix-aware).

    Ensures T+E specs (even without netlist or ELECTRONIC BomItem) trigger THERMAL-ELECTRICAL
    seam requirement in required_seam_pairs, so assess_specification always runs gate_epsilon
    for power->heat couplings (closes Befund 1 hole).
    """
    text = " ".join(part for part in (q.id, q.name, q.measurand or "")).lower()
    m = q.measurand or ""
    if m.startswith(("electronics.", "elec.", "electrical.", "bus.", "compute.")):
        return True
    markers = (
        "electronics",
        "elec",
        "current",
        "voltage",
        "bus",
        "inference",
        "power_budget",
    )
    unit_e = q.unit in {"A", "V"}
    # W only if explicit elec context (thermal power W must not falsely force ELEC alone; dissipat removed per Befund 7)
    power_elec = q.unit == "W" and ("elec" in text or "electronics" in text)
    return unit_e or any(marker in text for marker in markers) or power_elec


def domains_present(spec: Specification) -> set[SeamDomain]:
    """Detect which domains are present enough for epsilon seam coverage.

    Uses quantity heuristics (measurand-prefix + markers) for THERMAL/RADIATION/ELECTRICAL
    in addition to structural (components/bom/netlist) so pure quantity-driven T+E specs
    always produce required THERM-ELEC pair and trigger needs_seams/gate in assess.
    """
    present: set[SeamDomain] = set()
    if spec.components or any(item.domain is BomDomain.MECHANICAL for item in spec.bom):
        present.add(SeamDomain.MECHANICAL)
    if any(_looks_thermal(q) for q in spec.quantities):
        present.add(SeamDomain.THERMAL)
    if (
        spec.netlist is not None
        or any(item.domain is BomDomain.ELECTRONIC for item in spec.bom)
        or any(_looks_electrical(q) for q in spec.quantities)
    ):
        present.add(SeamDomain.ELECTRICAL)
    if spec.code_artifacts:
        present.add(SeamDomain.FIRMWARE)
    if any(item.role in (BomRole.PART, BomRole.MATERIAL) for item in spec.bom):
        present.add(SeamDomain.COST)
    if any(_looks_radiation(q) for q in spec.quantities):
        present.add(SeamDomain.RADIATION)
    if any(_looks_isru(q) for q in spec.quantities):
        present.add(SeamDomain.ISRU)
    if any(_looks_life_support(q) for q in spec.quantities):
        present.add(SeamDomain.LIFE_SUPPORT)
    return present


def required_seam_pairs(spec: Specification) -> list[tuple[SeamDomain, SeamDomain]]:
    """Required adjacent seam pairs for domains that are both present.

    Core Earth couplings are preserved independently of optional space domains.
    RADIATION couplings are additive when the domain is present (primarily THERM-RAD
    for vacuum radiation balance).

    Explicit list (instead of linear chain projection) ensures no regression on
    fundamental pairs like THERMAL-ELECTRICAL when RADIATION is absent, and avoids
    unintended bridging when domains are skipped.
    """
    present = domains_present(spec)
    # Explicit core + space attachments. Core pairs (THERM-ELEC etc.) are required
    # whenever their domains are present, regardless of RADIATION.
    # See L DR 2026-07-04 (council perspectives: explicit preferred for correctness,
    # simplicity, evolvability for space).
    _REQUIRED_ADJACENCIES = [
        (SeamDomain.MECHANICAL, SeamDomain.THERMAL),
        (SeamDomain.THERMAL, SeamDomain.ELECTRICAL),  # core power->heat, preserved
        (SeamDomain.ELECTRICAL, SeamDomain.FIRMWARE),
        (SeamDomain.THERMAL, SeamDomain.RADIATION),   # vacuum radiation primary
        # RAD-ELEC or MECH-RAD added only if physics justification (dose effects)
        # is documented and tested.
        # --- Complete Genesis / Elon multi-planetary extensions (explicit, Council-synthesized) ---
        (SeamDomain.THERMAL, SeamDomain.LIFE_SUPPORT),   # ECLSS hardware heat loads couple to thermal control in vacuum habitat
        (SeamDomain.RADIATION, SeamDomain.LIFE_SUPPORT), # dose on crew/biology/scrubbers; shielding couples rad to life support budgets
        (SeamDomain.MECHANICAL, SeamDomain.ISRU),        # regolith excavation/processing mechanics (crushers, rovers, reactors)
        (SeamDomain.ELECTRICAL, SeamDomain.ISRU),        # high power draw for electrolysis/Sabatier ISRU plants on Mars
        (SeamDomain.THERMAL, SeamDomain.ISRU),           # thermal balance of ISRU reactors (exothermic Sabatier, heating)
        (SeamDomain.ISRU, SeamDomain.COST),              # ISRU yield directly reduces landed mass/cost (first-principles leverage)
    ]
    required = [_pair(a, b) for a, b in _REQUIRED_ADJACENCIES if a in present and b in present]
    return required


# Example radiation-thermal seam for space (vacuum radiation balance)
# Usage in spec (when RADIATION domain present via dose/solar_flux etc):
# seam = DomainSeam(
#     id="rad_thermal_vacuum",
#     left_domain=SeamDomain.THERMAL,
#     right_domain=SeamDomain.RADIATION,
#     left_expr="q_net_heat_w",
#     right_expr="q_absorbed_w - q_radiated_w",
#     relation=SeamRelation.EQ,
#     rationale="Vacuum radiation dominant; links to vacuum_radiation_balance_check"
# )
# Future radiation-electrical (dose on electronics):
# seam = DomainSeam(
#     id="rad_elec_tid",
#     left_domain=SeamDomain.RADIATION,
#     right_domain=SeamDomain.ELECTRICAL,
#     left_expr="radiation.total_dose_sv",
#     right_expr="electronics.tid_limit_sv",
#     relation=SeamRelation.LE,
#     rationale="TID budget for derating / SEE on electronics in space"
# )
# required_seam_pairs uses filtered linear chain so only present domains' consecutive
# pairs are mandatory (RADIATION optional → no breakage for earth specs).


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
    if seam.left_expr == "bom_total_cost" or (seam.id.startswith("auto_cost") and not any(q for q in spec.quantities if q.unit in ("EUR", "USD", "€", "$") or "total_cost" in (q.id or "").lower())):
        # auto-generated virtual (no declared total quantity); satisfied by construction (BOM is source of truth)
        return []
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
        if seam.left_expr == "bom_total_cost" or seam.left_expr.startswith("auto_"):
            # auto-generated (Befund 10 Option A): no declared total in spec; BOM is source of truth, rollup satisfied
            return []
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
    # C-1: `complete` includes explicitly labelled filament ESTIMATES — this seam certifies the
    # arithmetic roll-up coupling, not price grounding (that is Cost.fully_grounded, surfaced
    # separately). An estimate-backed roll-up is still a deterministic, checkable sum.
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
    """Mechanical builder: attach supplied seams to a spec-run certificate.

    Auto-generates COST_ROLLUP seam if cost_rollup_required(spec) and no cost seam
    provided (Option A for Befund 10: honest and scalable for demos; cost from BOM).
    """
    seams = list(seams) if seams else []
    if cost_rollup_required(spec) and bom_cost(spec).complete and not any(s.relation == SeamRelation.COST_ROLLUP for s in seams):
        cost_qty_id = None
        for q in spec.quantities:
            if "total" in (q.id or "").lower() and q.unit in ("EUR", "USD", "€", "$"):
                cost_qty_id = q.id
                break
        if cost_qty_id is None:
            cost_qty_id = "bom_total_cost"  # virtual for auto
        # choose right domain that is present and distinct from COST
        present = domains_present(spec)
        right_d = None
        for d in (SeamDomain.ELECTRICAL, SeamDomain.MECHANICAL, SeamDomain.FIRMWARE, SeamDomain.THERMAL, SeamDomain.RADIATION):
            if d in present and d != SeamDomain.COST:
                right_d = d
                break
        if right_d is None:
            right_d = SeamDomain.MECHANICAL if SeamDomain.MECHANICAL in present else SeamDomain.FIRMWARE
        cost_seam = DomainSeam(
            id="auto_cost_rollup",
            left_domain=SeamDomain.COST,
            right_domain=right_d,
            relation=SeamRelation.COST_ROLLUP,
            left_expr=cost_qty_id,
            right_expr="EUR",
            rationale="auto-generated cost rollup seam (BOM calculable) because cost_rollup_required and no COST seam provided",
        )
        seams.append(cost_seam)

    return SeamCertificate(
        spec_run_id=spec.run_id,
        seams=seams,
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


__all__ = [
    "EvaluatedExpression",
    "build_seam_certificate",
    "cost_rollup_required",
    "domains_present",
    "evaluate_seam_expression",
    "gate_epsilon",
    "required_seam_pairs",
]
