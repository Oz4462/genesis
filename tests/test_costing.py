"""Tests for the BOM cost roll-up — honest, never an invented total.

Cost = Σ count × claim-backed unit-price, per currency. Unpriced PART/MATERIAL
items make the total a partial lower bound (listed). Mixed currencies yield
per-currency subtotals, never an invented FX conversion.

Run:  pytest tests/test_costing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.state import (  # noqa: E402
    BomItem,
    BomRole,
    Quantity,
    Sourcing,
    Specification,
    ValueOrigin,
)
from gen.costing import bom_cost, format_cost  # noqa: E402


def _price(qid: str, value: float, unit: str = "EUR") -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.GROUNDED, grounding=["c"])


def _sourced(bid: str, count: int, price_id: str | None) -> BomItem:
    sourcing = None
    if price_id is not None:
        sourcing = Sourcing(supplier="S", part_number="P", price_quantity_id=price_id,
                            grounding=["c"])
    return BomItem(id=bid, name=bid, role=BomRole.PART, count=count, sourcing=sourcing)


def test_single_currency_total():
    spec = Specification(
        run_id="r", idea="i",
        quantities=[_price("q_screw", 0.42), _price("q_nut", 0.10)],
        bom=[_sourced("b_screw", 4, "q_screw"), _sourced("b_nut", 4, "q_nut")],
    )
    cost = bom_cost(spec)
    assert cost.subtotals == {"EUR": 4 * 0.42 + 4 * 0.10}
    assert cost.complete and cost.priced_count == 2


def test_unpriced_part_makes_it_partial():
    spec = Specification(
        run_id="r", idea="i",
        quantities=[_price("q_screw", 0.42)],
        bom=[_sourced("b_screw", 2, "q_screw"), _sourced("b_bracket", 1, None)],
    )
    cost = bom_cost(spec)
    assert cost.subtotals == {"EUR": 0.84}
    assert not cost.complete and cost.unpriced == ["b_bracket"]
    assert "unvollständig" in format_cost(cost) and "b_bracket" in format_cost(cost)


def test_mixed_currencies_are_kept_separate():
    spec = Specification(
        run_id="r", idea="i",
        quantities=[_price("q_eur", 1.0, "EUR"), _price("q_usd", 2.0, "USD")],
        bom=[_sourced("b1", 1, "q_eur"), _sourced("b2", 3, "q_usd")],
    )
    cost = bom_cost(spec)
    assert cost.subtotals == {"EUR": 1.0, "USD": 6.0}     # no invented FX total


def test_tools_are_not_counted_as_unpriced():
    tool = BomItem(id="b_tool", name="hex key", role=BomRole.TOOL, count=1)
    spec = Specification(run_id="r", idea="i", quantities=[_price("q", 5.0)],
                         bom=[_sourced("b_part", 1, "q"), tool])
    cost = bom_cost(spec)
    assert cost.complete                                   # the tool is not a buyable part
    assert cost.subtotals == {"EUR": 5.0}


def test_no_prices_at_all():
    spec = Specification(run_id="r", idea="i",
                         bom=[BomItem(id="b", name="x", role=BomRole.PART)])
    cost = bom_cost(spec)
    assert cost.subtotals == {} and not cost.complete
    assert "nicht beweisbar" in format_cost(cost)
