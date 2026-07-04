"""Deterministic completeness critic for a γ specification.

GATE γ proves a spec is SOUND (no fabricated value, no dangling reference, etc.).
This critic asks a softer, orthogonal question: is the plan COMPLETE? It surfaces
warnings — never hard failures — for things that are valid but probably
under-specified: a quantity declared but never used, a tool nobody picks up, a
component with no BOM line, or a build that never produces a final artifact —
plus positive floors (no steps / no BOM / no artifact at all), so an EMPTY spec
never reads as "complete".

Warnings are surfaced to the human (CLI / Markdown); they do not block a spec,
because a valid spec may legitimately carry an informational quantity. The critic
is deterministic and LLM-free.
"""

from __future__ import annotations

from .core.errors import FormulaError
from .core.state import BomRole, GeometryNode, Specification
from .costing import FILAMENT_PRICE_MEASURAND
from .verification.derivation import referenced_names


def _geometry_quantity_ids(node: GeometryNode, out: set[str]) -> None:
    out.update(node.params.values())
    for child in node.children:
        _geometry_quantity_ids(child, out)


def _referenced_quantity_ids(spec: Specification) -> set[str]:
    refs: set[str] = set()
    for q in spec.quantities:
        if q.derivation is not None:
            refs.update(q.derivation.inputs)
    for comp in spec.components:
        refs.update(comp.quantity_ids)
        if comp.material_density:
            refs.add(comp.material_density)
        if comp.geometry is not None:
            _geometry_quantity_ids(comp.geometry, refs)
    for k in spec.constraints:
        try:
            refs |= referenced_names(k.left) | referenced_names(k.right)
        except FormulaError:  # a malformed constraint is a γ failure, not ours
            pass
    for s in spec.steps:
        refs.update(s.quantity_refs)
        if s.torque_quantity_id:
            refs.add(s.torque_quantity_id)
    for item in spec.bom:
        if item.sourcing is not None and item.sourcing.price_quantity_id:
            refs.add(item.sourcing.price_quantity_id)
    if spec.site is not None and spec.site.available_space is not None:
        refs.update(spec.site.available_space)
    # measurand-based consumption: costing.bom_cost reads the filament price BY MEASURAND
    # (costing.FILAMENT_PRICE_MEASURAND), not by id — such a quantity is consumed, not an orphan
    for q in spec.quantities:
        if q.measurand == FILAMENT_PRICE_MEASURAND:
            refs.add(q.id)
    # Phase-ε consumption: a spec-carried seam certificate references quantities in its
    # seam expressions (gate_epsilon evaluates them) — those are consumed, not orphans
    cert = getattr(spec, "seam_certificate", None)
    if cert is not None:
        for seam in cert.seams:
            for expr in (seam.left_expr, seam.right_expr):
                try:
                    refs |= referenced_names(expr)
                except FormulaError:  # non-formula side (e.g. COST_ROLLUP "EUR")
                    pass
    return refs


def completeness_warnings(spec: Specification) -> list[str]:
    """Soft, deterministic completeness warnings (empty if the plan is complete)."""
    warnings: list[str] = []

    # 0. positive floors — a purely negative critic would call an EMPTY spec "complete".
    #    These are soft warnings (an abstention spec legitimately stays empty and says so
    #    in `gaps`); they make the emptiness visible, they never block.
    if not spec.steps:
        warnings.append("der Bau hat keine Schritte (kein ausführbarer Plan)")
    if not spec.bom:
        warnings.append("keine Stückliste (kein Teil und kein Werkzeug benannt)")
    if not spec.components and not any(s.outputs for s in spec.steps):
        warnings.append(
            "der Bau erzeugt kein Artefakt (weder Bauteile noch Schritt-Outputs deklariert)"
        )

    # 1. orphan quantities — declared but never referenced anywhere
    referenced = _referenced_quantity_ids(spec)
    for q in spec.quantities:
        if q.id not in referenced:
            warnings.append(f"Größe {q.id!r} ({q.name}) ist deklariert, wird aber nirgends verwendet")

    # 2. tools nobody uses
    used_bom = {bid for s in spec.steps for bid in s.uses}
    for item in spec.bom:
        if item.role is BomRole.TOOL and item.id not in used_bom:
            warnings.append(
                f"Werkzeug {item.id!r} ({item.name}) steht in der Stückliste, "
                "wird aber von keinem Schritt verwendet"
            )

    # 3. fabricated components with no BOM line
    bom_component_ids = {b.component_id for b in spec.bom if b.component_id}
    for comp in spec.components:
        if comp.geometry is not None and comp.id not in bom_component_ids:
            warnings.append(
                f"Bauteil {comp.id!r} ({comp.name}) hat Geometrie, "
                "aber keine Stücklisten-Position"
            )

    # 4. the build produces no final artifact (an output never consumed downstream)
    if spec.steps:
        produced: set[str] = set()
        consumed: set[str] = set()
        for s in spec.steps:
            produced.update(s.outputs)
            consumed.update(s.inputs)
        if produced and not (produced - consumed):
            warnings.append(
                "der Bau erzeugt kein finales Artefakt "
                "(jedes Zwischenergebnis wird wieder verbraucht)"
            )

    return warnings
