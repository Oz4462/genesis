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
    Component,
    GeometryNode,
    Quantity,
    Sourcing,
    Specification,
    ValueOrigin,
)
from gen.costing import FILAMENT_PRICE_MEASURAND, bom_cost, format_cost  # noqa: E402


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


# --- C-2: only GROUNDED prices count as priced (GATE γ C-16) ---------------------


def test_ungrounded_price_is_not_counted_as_priced():
    """A DECISION-origin price is a choice, not a claim-backed price — the item stays
    unpriced (partial lower bound) and the reason is surfaced as an honest note."""
    decided = Quantity(id="q_guess", name="q_guess", value=9.99, unit="EUR",
                       origin=ValueOrigin.DECISION, rationale="gewählt, nicht belegt")
    spec = Specification(
        run_id="r", idea="i",
        quantities=[_price("q_ok", 1.0), decided],
        bom=[_sourced("b_ok", 1, "q_ok"), _sourced("b_guess", 2, "q_guess")],
    )
    cost = bom_cost(spec)
    assert cost.subtotals == {"EUR": 1.0}          # the decided price is NOT summed
    assert "b_guess" in cost.unpriced and not cost.complete
    assert any("b_guess" in n and "GROUNDED" in n for n in cost.notes)
    assert cost.priced_count == 1


# --- C-1: filament-costed (fabricated) parts are explicit ESTIMATES --------------


def _fabricated_spec(filament_origin: ValueOrigin = ValueOrigin.GROUNDED) -> Specification:
    """One printed part (10×10×10 mm box, density 0.00124 g/mm³) plus one purchased part."""
    geom = GeometryNode(kind="box", params={"size_x": "q_s", "size_y": "q_s", "size_z": "q_s"})
    q_s = Quantity(id="q_s", name="q_s", value=10.0, unit="mm",
                   origin=ValueOrigin.DECISION, rationale="t")
    q_rho = Quantity(id="q_rho", name="q_rho", value=0.00124, unit="g/mm^3",
                     origin=ValueOrigin.GROUNDED, grounding=["c"])
    if filament_origin is ValueOrigin.GROUNDED:
        q_fil = Quantity(id="q_fil", name="q_fil", value=0.05, unit="EUR/g",
                         origin=ValueOrigin.GROUNDED, grounding=["c"],
                         measurand=FILAMENT_PRICE_MEASURAND)
    else:
        q_fil = Quantity(id="q_fil", name="q_fil", value=0.05, unit="EUR/g",
                         origin=ValueOrigin.DECISION, rationale="Marktannahme",
                         measurand=FILAMENT_PRICE_MEASURAND)
    comp = Component(id="c_part", name="part", geometry=geom, material_density="q_rho")
    return Specification(
        run_id="r", idea="i",
        quantities=[q_s, q_rho, q_fil, _price("q_bolt", 0.42)],
        components=[comp],
        bom=[BomItem(id="b_print", name="printed", role=BomRole.PART, count=1,
                     component_id="c_part"),
             _sourced("b_bolt", 4, "q_bolt")],
    )


def test_fabricated_part_is_flagged_as_estimate_not_as_proven_price():
    cost = bom_cost(_fabricated_spec())
    assert cost.fabricated == ["b_print"]
    assert cost.estimated_count == 1 and cost.fabricated_estimated
    # complete: every position is either grounded-priced or an EXPLICIT estimate …
    assert cost.complete and cost.unpriced == []
    # … but fully_grounded is honest: an estimate is not a proven price
    assert not cost.fully_grounded
    # expected: 1000 mm³ × 0.4 infill × 0.00124 g/mm³ × 0.05 EUR/g + 4 × 0.42
    assert cost.subtotals["EUR"] == 1000 * 0.4 * 0.00124 * 0.05 + 4 * 0.42
    assert "geschätzt aus Filament" in format_cost(cost)
    assert "alle Teile bepreist" not in format_cost(cost)   # the old lying label is gone


def test_purchased_only_spec_is_fully_grounded():
    spec = Specification(
        run_id="r", idea="i",
        quantities=[_price("q", 5.0)],
        bom=[_sourced("b", 1, "q")],
    )
    cost = bom_cost(spec)
    assert cost.complete and cost.fully_grounded and not cost.fabricated_estimated
    assert "belegtem Preis" in format_cost(cost)


def test_decision_filament_price_still_estimates_with_flag():
    """A DECISION filament price does not break the estimate path: the position is
    already an explicit estimate (C-1 flag), never a claim-backed price."""
    cost = bom_cost(_fabricated_spec(filament_origin=ValueOrigin.DECISION))
    assert cost.fabricated == ["b_print"] and cost.fabricated_estimated
    assert not cost.fully_grounded


# --- C-3: a negative count must never subtract money -----------------------------


def test_negative_count_is_flagged_not_subtracted():
    spec = Specification(
        run_id="r", idea="i",
        quantities=[_price("q_a", 10.0), _price("q_b", 1.0)],
        bom=[_sourced("b_ok", 1, "q_a"), _sourced("b_neg", -3, "q_b")],
    )
    cost = bom_cost(spec)
    assert cost.subtotals == {"EUR": 10.0}         # -3 × 1.0 was NOT subtracted
    assert "b_neg" in cost.unpriced and not cost.complete
    assert any("b_neg" in n and "Stückzahl" in n for n in cost.notes)
