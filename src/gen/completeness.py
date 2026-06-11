"""Deterministic completeness critic for a γ specification.

GATE γ proves a spec is SOUND (no fabricated value, no dangling reference, etc.).
This critic asks a softer, orthogonal question: is the plan COMPLETE? It surfaces
warnings — never hard failures — for things that are valid but probably
under-specified: a quantity declared but never used, a tool nobody picks up, a
component with no BOM line, or a build that never produces a final artifact.

Warnings are surfaced to the human (CLI / Markdown); they do not block a spec,
because a valid spec may legitimately carry an informational quantity. The critic
is deterministic and LLM-free.
"""

from __future__ import annotations

from .core.state import BomRole, GeometryNode, Specification
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
        except Exception:  # noqa: BLE001 - a malformed constraint is a γ failure, not ours
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
    return refs


def completeness_warnings(spec: Specification) -> list[str]:
    """Soft, deterministic completeness warnings (empty if the plan is complete)."""
    warnings: list[str] = []

    # 1. orphan quantities — declared but never referenced anywhere
    referenced = _referenced_quantity_ids(spec)
    for q in spec.quantities:
        if q.id not in referenced:
            warnings.append(f"quantity {q.id!r} ({q.name}) is declared but never used")

    # 2. tools nobody uses
    used_bom = {bid for s in spec.steps for bid in s.uses}
    for item in spec.bom:
        if item.role is BomRole.TOOL and item.id not in used_bom:
            warnings.append(f"tool {item.id!r} ({item.name}) is in the BOM but used by no step")

    # 3. fabricated components with no BOM line
    bom_component_ids = {b.component_id for b in spec.bom if b.component_id}
    for comp in spec.components:
        if comp.geometry is not None and comp.id not in bom_component_ids:
            warnings.append(f"component {comp.id!r} ({comp.name}) has geometry but no BOM line")

    # 4. the build produces no final artifact (an output never consumed downstream)
    if spec.steps:
        produced: set[str] = set()
        consumed: set[str] = set()
        for s in spec.steps:
            produced.update(s.outputs)
            consumed.update(s.inputs)
        if produced and not (produced - consumed):
            warnings.append("the build produces no final artifact (every output is consumed again)")

    return warnings
