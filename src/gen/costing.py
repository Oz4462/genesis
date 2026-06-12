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

from .core.state import BomRole, Specification


@dataclass(frozen=True)
class Cost:
    """A BOM cost estimate. `subtotals` maps currency -> total (count × price) over
    priced items. `unpriced` lists PART/MATERIAL item ids that carry no grounded
    price (so the estimate is a partial lower bound). `complete` is True only when
    every PART/MATERIAL item is priced. GENESIS reports a partial, never a guessed
    total."""

    subtotals: dict[str, float] = field(default_factory=dict)
    unpriced: list[str] = field(default_factory=list)
    priced_count: int = 0

    @property
    def complete(self) -> bool:
        return not self.unpriced


def bom_cost(spec: Specification) -> Cost:
    """Roll up the BOM cost per currency. Counts count × price for items whose
    sourcing references an existing price quantity; flags unpriced PART/MATERIAL.
    """
    quantities = {q.id: q for q in spec.quantities}
    subtotals: dict[str, float] = {}
    unpriced: list[str] = []
    priced = 0

    for item in spec.bom:
        price_q = None
        if item.sourcing is not None and item.sourcing.price_quantity_id:
            price_q = quantities.get(item.sourcing.price_quantity_id)
        if price_q is not None:
            currency = price_q.unit.strip() or "?"
            subtotals[currency] = subtotals.get(currency, 0.0) + item.count * float(price_q.value)
            priced += 1
        elif item.role in (BomRole.PART, BomRole.MATERIAL):
            unpriced.append(item.id)

    return Cost(subtotals=subtotals, unpriced=unpriced, priced_count=priced)


def format_cost(cost: Cost) -> str:
    """One-line human summary of the cost roll-up (German — a result string)."""
    if not cost.subtotals:
        return "keine bepreisten Teile (Kosten nicht beweisbar — braucht claim-belegte Preise)"
    parts = ", ".join(f"{total:g} {cur}" for cur, total in sorted(cost.subtotals.items()))
    if cost.complete:
        return f"{parts} (alle Teile bepreist)"
    return f"{parts} (unvollständig — ohne Preis: {', '.join(cost.unpriced)})"
