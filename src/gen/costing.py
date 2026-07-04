"""Deterministic BOM cost roll-up — honest about what is priced and what is ESTIMATED.

The total build cost is the sum of count × unit-price over BOM items that carry a
claim-backed price (a GROUNDED price quantity, verbatim from a claim — GATE γ
C-16; any other origin is a choice, not a proven price, and does NOT count). With
the same honesty as the rest of GENESIS: the total is reported only over PRICED
items; any unpriced PART/MATERIAL makes the total a partial lower bound (listed,
never invented). A fabricated (printed) part may be costed from filament — that is
an explicit, labelled ESTIMATE (bbox × infill × density × filament price), never a
proven price; consumers must surface the label. Prices are grouped by currency —
GENESIS never applies an invented FX rate, so a grand total is given only within
one currency.

There is no gate here: cost is a property surfaced to the human, like volume/mass.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .core.state import BomRole, Component, GeometryNode, Quantity, Specification, ValueOrigin

#: Default print infill for the filament-cost estimate of a fabricated part — a process assumption
#: (a sparse-but-structural 40 %), not a factual claim. The estimate is a bounding-box upper bound.
FABRICATION_INFILL = 0.4

#: Measurand a spec uses to declare the filament price (currency per gram) for fabricated parts.
FILAMENT_PRICE_MEASURAND = "material.filament_price"


@dataclass(frozen=True)
class Cost:
    """A BOM cost roll-up with an honest priced/estimated/unpriced split.

    `subtotals` maps currency -> total (count × price) over priced items. `unpriced`
    lists PART/MATERIAL item ids that carry neither a grounded price nor a computable
    filament estimate (so the total is a partial lower bound). `fabricated` lists item
    ids costed from filament (volume × infill × density × price/g) — these are explicit
    ESTIMATES, counted in `estimated_count`, never claim-backed prices. `notes` carries
    honest per-item diagnostics (an ungrounded price, a negative count). `complete` is
    True when every PART/MATERIAL position is either GROUNDED-priced or an explicitly
    labelled estimate — it does NOT mean every price is proven; `fully_grounded` is the
    stricter, proof-level property. GENESIS reports a partial, never a guessed total."""

    subtotals: dict[str, float] = field(default_factory=dict)
    unpriced: list[str] = field(default_factory=list)
    priced_count: int = 0
    fabricated: list[str] = field(default_factory=list)
    estimated_count: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """Every PART/MATERIAL position is accounted for — grounded-priced OR an
        explicitly labelled filament estimate. NOT a claim that all prices are proven."""
        return not self.unpriced

    @property
    def fabricated_estimated(self) -> bool:
        """True when any position in the roll-up is a filament ESTIMATE (not a price)."""
        return self.estimated_count > 0

    @property
    def fully_grounded(self) -> bool:
        """True only when the roll-up is complete AND contains no estimate — every
        position carries a GROUNDED purchase price (the proof-level property)."""
        return self.complete and self.estimated_count == 0


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
    """Roll up the BOM cost per currency. Purchased items are counted count × GROUNDED price —
    a price quantity with any other origin is a choice, not a claim-backed price (GATE γ C-16),
    so the item stays unpriced with an honest note. A FABRICATED part (a PART with a
    ``component_id``) is costed from filament — bbox volume × infill × material density × a
    declared filament price (EUR/g, measurand ``material.filament_price``) — as an explicit,
    labelled ESTIMATE (``fabricated``/``estimated_count``), so an in-house-printed part is
    neither mislabelled an unpriced purchase nor passed off as a proven price. A negative
    ``count`` is defensively flagged (a position must never subtract money). Items with neither
    a grounded price nor a computable filament estimate remain flagged unpriced (a partial
    lower bound, never invented).
    """
    quantities = {q.id: q for q in spec.quantities}
    components = {c.id: c for c in spec.components}
    filament = next((q for q in spec.quantities if q.measurand == FILAMENT_PRICE_MEASURAND), None)
    subtotals: dict[str, float] = {}
    unpriced: list[str] = []
    fabricated: list[str] = []
    notes: list[str] = []
    priced = 0
    estimated = 0

    for item in spec.bom:
        # 0) defensive: a negative count would SUBTRACT money from the roll-up — flag, never sum
        if item.count < 0:
            notes.append(
                f"Position {item.id!r}: negative Stückzahl ({item.count}) — "
                "nicht verrechnet (eine Position darf den Roll-up nie verringern)"
            )
            if item.role in (BomRole.PART, BomRole.MATERIAL):
                unpriced.append(item.id)
            continue
        # 1) purchased part with a GROUNDED sourcing price (any other origin is not a price proof)
        price_q = None
        if item.sourcing is not None and item.sourcing.price_quantity_id:
            price_q = quantities.get(item.sourcing.price_quantity_id)
        if price_q is not None and price_q.origin is not ValueOrigin.GROUNDED:
            notes.append(
                f"Position {item.id!r}: Preisgröße {price_q.id!r} hat Origin "
                f"{price_q.origin.value!r}, nicht GROUNDED — zählt nicht als belegter Preis (C-16)"
            )
            price_q = None
        if price_q is not None:
            currency = price_q.unit.strip() or "?"
            subtotals[currency] = subtotals.get(currency, 0.0) + item.count * float(price_q.value)
            priced += 1
            continue
        # 2) fabricated (printed) part — filament MATERIAL-COST ESTIMATE, if a filament price is
        #    declared. Always labelled an estimate, regardless of the filament price's origin.
        comp: Component | None = components.get(item.component_id) if item.component_id else None
        if filament is not None and comp is not None and comp.material_density:
            density_q = quantities.get(comp.material_density)
            volume = _bbox_volume_mm3(comp.geometry, quantities)
            if density_q is not None and volume is not None:
                grams = volume * FABRICATION_INFILL * float(density_q.value)
                currency = filament.unit.split("/")[0].strip() or "?"
                subtotals[currency] = subtotals.get(currency, 0.0) + item.count * grams * float(filament.value)
                priced += 1
                estimated += 1
                fabricated.append(item.id)
                continue
        # 3) genuinely unpriced PART/MATERIAL (a partial lower bound, surfaced)
        if item.role in (BomRole.PART, BomRole.MATERIAL):
            unpriced.append(item.id)

    return Cost(subtotals=subtotals, unpriced=unpriced, priced_count=priced,
                fabricated=fabricated, estimated_count=estimated, notes=notes)


def format_cost(cost: Cost) -> str:
    """One-line human summary of the cost roll-up (German — a result string). Estimates are
    always labelled („geschätzt aus Filament") — a complete roll-up with estimates never reads
    as if every price were proven."""
    if not cost.subtotals:
        return "keine bepreisten Teile (Kosten nicht beweisbar — braucht claim-belegte Preise)"
    parts = ", ".join(f"{total:g} {cur}" for cur, total in sorted(cost.subtotals.items()))
    fab = (f"; {len(cost.fabricated)} gedruckte Teile geschätzt aus Filament "
           "(Schätzung, kein belegter Preis)" if cost.fabricated else "")
    note = f"; Hinweise: {' | '.join(cost.notes)}" if cost.notes else ""
    if cost.fully_grounded:
        return f"{parts} (alle Teile mit belegtem Preis){note}"
    if cost.complete:
        return f"{parts} (alle Positionen erfasst{fab}){note}"
    return f"{parts} (unvollständig — ohne Preis: {', '.join(cost.unpriced)}{fab}){note}"
