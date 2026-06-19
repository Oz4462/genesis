"""Deterministic BOM cost roll-up — honest about what is priced.

The total build cost is the sum of count × unit-price over BOM items that carry a
claim-backed price (a GROUNDED price quantity, verbatim from a claim — GATE γ
C-16). With the same honesty as the rest of GENESIS: the total is reported only
over PRICED items; any unpriced PART/MATERIAL makes the total a partial lower
bound (listed, never invented). Prices are grouped by currency — GENESIS never
applies an invented FX rate, so a grand total is given only within one currency.

There is no gate here: cost is a property surfaced to the human, like volume/mass.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .core.state import BomRole, Component, GeometryNode, Quantity, Specification

#: Default print infill for the filament-cost estimate of a fabricated part — a process assumption
#: (a sparse-but-structural 40 %), not a factual claim. The estimate is a bounding-box upper bound.
FABRICATION_INFILL = 0.4

#: Measurand a spec uses to declare the filament price (currency per gram) for fabricated parts.
FILAMENT_PRICE_MEASURAND = "material.filament_price"


@dataclass(frozen=True)
class Cost:
    """A BOM cost estimate. `subtotals` maps currency -> total (count × price) over
    priced items. `unpriced` lists PART/MATERIAL item ids that carry no grounded
    price (so the estimate is a partial lower bound). `complete` is True only when
    every PART/MATERIAL item is priced. `fabricated` lists item ids costed from
    filament (volume × density × price/g), not purchased. GENESIS reports a partial,
    never a guessed total."""

    subtotals: dict[str, float] = field(default_factory=dict)
    unpriced: list[str] = field(default_factory=list)
    priced_count: int = 0
    fabricated: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.unpriced


def _bbox_volume_mm3(geometry: GeometryNode | None, quantities: dict[str, Quantity]) -> float | None:
    """Bounding-box volume [mm³] of a fabricated part: walk to the root ``box`` and multiply its
    size_x·size_y·size_z (an UPPER bound — bores/voids are ignored, so the filament estimate is
    conservative/high). Returns None if there is no resolvable box."""
    node = geometry
    while node is not None and node.kind != "box":
        node = node.children[0] if node.children else None
    if node is None:
        return None
    try:
        return (float(quantities[node.params["size_x"]].value)
                * float(quantities[node.params["size_y"]].value)
                * float(quantities[node.params["size_z"]].value))
    except (KeyError, AttributeError, TypeError, ValueError):
        return None


def bom_cost(spec: Specification) -> Cost:
    """Roll up the BOM cost per currency. Purchased items are counted count × grounded price. A
    FABRICATED part (a PART with a ``component_id``) is costed from filament — bbox volume × infill
    × material density × a declared filament price (EUR/g, measurand ``material.filament_price``) —
    so an in-house-printed part is NOT mislabelled an unpriced purchase. Items with neither a price
    nor a computable filament cost remain flagged unpriced (a partial lower bound, never invented).
    """
    quantities = {q.id: q for q in spec.quantities}
    components = {c.id: c for c in spec.components}
    filament = next((q for q in spec.quantities if q.measurand == FILAMENT_PRICE_MEASURAND), None)
    subtotals: dict[str, float] = {}
    unpriced: list[str] = []
    fabricated: list[str] = []
    priced = 0

    for item in spec.bom:
        # 1) purchased part with a grounded sourcing price
        price_q = None
        if item.sourcing is not None and item.sourcing.price_quantity_id:
            price_q = quantities.get(item.sourcing.price_quantity_id)
        if price_q is not None:
            currency = price_q.unit.strip() or "?"
            subtotals[currency] = subtotals.get(currency, 0.0) + item.count * float(price_q.value)
            priced += 1
            continue
        # 2) fabricated (printed) part — material cost from filament, if a filament price is declared
        comp: Component | None = components.get(item.component_id) if item.component_id else None
        if filament is not None and comp is not None and comp.material_density:
            density_q = quantities.get(comp.material_density)
            volume = _bbox_volume_mm3(comp.geometry, quantities)
            if density_q is not None and volume is not None:
                grams = volume * FABRICATION_INFILL * float(density_q.value)
                currency = filament.unit.split("/")[0].strip() or "?"
                subtotals[currency] = subtotals.get(currency, 0.0) + item.count * grams * float(filament.value)
                priced += 1
                fabricated.append(item.id)
                continue
        # 3) genuinely unpriced PART/MATERIAL (a partial lower bound, surfaced)
        if item.role in (BomRole.PART, BomRole.MATERIAL):
            unpriced.append(item.id)

    return Cost(subtotals=subtotals, unpriced=unpriced, priced_count=priced, fabricated=fabricated)


def format_cost(cost: Cost) -> str:
    """One-line human summary of the cost roll-up (German — a result string)."""
    if not cost.subtotals:
        return "keine bepreisten Teile (Kosten nicht beweisbar — braucht claim-belegte Preise)"
    parts = ", ".join(f"{total:g} {cur}" for cur, total in sorted(cost.subtotals.items()))
    fab = f"; {len(cost.fabricated)} gedruckte Teile als Filament-Materialkosten" if cost.fabricated else ""
    if cost.complete:
        return f"{parts} (alle Teile bepreist{fab})"
    return f"{parts} (unvollständig — ohne Preis: {', '.join(cost.unpriced)}{fab})"
