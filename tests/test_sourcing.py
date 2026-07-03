"""Tests for sourcing BOM (GATE γ C-16) — no invented shop, part, or price.

A BOM sourcing (supplier / order number / price) is a factual claim about the
world, so it must be claim-backed: the grounding is VERIFIED, supplier and
part_number appear verbatim in a grounding claim, and the price is a GROUNDED
quantity (its number verbatim from a claim). An invented supplier or an
ungrounded price never reaches the output — in doubt, the sourcing is an honest
gap. These tests prove the mechanism with a scripted claim world (real sourcing
data comes from live α-research later).

Run:  pytest tests/test_sourcing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import UnsourcedSourcingError  # noqa: E402
from gen.core.state import (  # noqa: E402
    BomItem,
    BomRole,
    Claim,
    ClaimStatus,
    Question,
    Quantity,
    RunState,
    Sourcing,
    SourceRef,
    SourceSupport,
    Specification,
    ValueOrigin,
)
from gen.verification.gates import gate_gamma, text_in_claim  # noqa: E402


def _claim(cid: str, text: str, *, status=ClaimStatus.VERIFIED, conf=0.9) -> Claim:
    return Claim(
        id=cid, text=text,
        sources=[SourceRef(f"https://{cid}", True, support=SourceSupport.SUPPORTS)],
        status=status, confidence=conf,
        verification=[SourceRef(f"https://i/{cid}", True, support=SourceSupport.SUPPORTS)]
        if status is ClaimStatus.VERIFIED else [],
    )


# the scripted claim world: a real supplier line + a real price
SUPPLIER_CLAIM = _claim(
    "c_src", "McMaster-Carr lists part 91290A115, an M4x16 socket head screw.")
PRICE_CLAIM = _claim(
    "c_price", "The M4x16 socket head screw costs 0.42 EUR per piece at McMaster-Carr.")


def _price_quantity(grounding=("c_price",)) -> Quantity:
    return Quantity(id="q_price", name="screw unit price", value=0.42, unit="EUR",
                    origin=ValueOrigin.GROUNDED, grounding=list(grounding))


def _state(bom_items, quantities, claims) -> RunState:
    st = RunState(question=Question(raw="i", run_id="r"))
    st.claims = claims
    st.specification = Specification(
        run_id="r", idea="i", quantities=quantities, bom=bom_items,
    )
    return st


def _codes(state) -> set[str]:
    return {f.code for f in gate_gamma(state).failures}


# --- the happy path: fully claim-backed sourcing ------------------------------

def test_grounded_sourcing_passes():
    item = BomItem(
        id="b_screw", name="M4x16 screw", role=BomRole.PART, count=4,
        sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                          price_quantity_id="q_price", grounding=["c_src", "c_price"]),
    )
    state = _state([item], [_price_quantity()], [SUPPLIER_CLAIM, PRICE_CLAIM])
    result = gate_gamma(state)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


# --- no invented shop / part --------------------------------------------------

def test_constructor_rejects_sourcing_without_grounding():
    with pytest.raises(UnsourcedSourcingError):
        Sourcing(supplier="Acme", part_number="X", grounding=[])


def test_invented_supplier_is_caught():
    item = BomItem(
        id="b_screw", name="screw", role=BomRole.PART,
        sourcing=Sourcing(supplier="Totally Fake Shop", part_number="91290A115",
                          grounding=["c_src"]),
    )
    state = _state([item], [], [SUPPLIER_CLAIM])
    assert "SOURCING_NOT_IN_CLAIM" in _codes(state)


def test_invented_part_number_is_caught():
    item = BomItem(
        id="b_screw", name="screw", role=BomRole.PART,
        sourcing=Sourcing(supplier="McMaster-Carr", part_number="99999INVENTED",
                          grounding=["c_src"]),
    )
    state = _state([item], [], [SUPPLIER_CLAIM])
    assert "SOURCING_NOT_IN_CLAIM" in _codes(state)


def test_unverified_grounding_is_caught():
    unverified = _claim("c_un", "Some shop maybe sells screws.", status=ClaimStatus.UNSUPPORTED)
    item = BomItem(
        id="b", name="screw", role=BomRole.PART,
        sourcing=Sourcing(supplier="Some shop", part_number="screws",
                          grounding=["c_un"]),
    )
    state = _state([item], [], [unverified])
    assert "SOURCING_NOT_GROUNDED" in _codes(state)


# --- no invented price --------------------------------------------------------

def test_invented_price_not_in_claim_is_caught():
    # price 9.99 does not appear in the price claim (which says 0.42)
    bad_price = Quantity(id="q_price", name="price", value=9.99, unit="EUR",
                         origin=ValueOrigin.GROUNDED, grounding=["c_price"])
    item = BomItem(
        id="b", name="screw", role=BomRole.PART,
        sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                          price_quantity_id="q_price", grounding=["c_src"]),
    )
    state = _state([item], [bad_price], [SUPPLIER_CLAIM, PRICE_CLAIM])
    assert "VALUE_NOT_IN_GROUNDING" in _codes(state)


def test_price_must_be_grounded_quantity_not_decision():
    decision_price = Quantity(id="q_price", name="price", value=0.42, unit="EUR",
                              origin=ValueOrigin.DECISION, rationale="guessed")
    item = BomItem(
        id="b", name="screw", role=BomRole.PART,
        sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                          price_quantity_id="q_price", grounding=["c_src"]),
    )
    state = _state([item], [decision_price], [SUPPLIER_CLAIM])
    assert "SOURCING_NOT_GROUNDED" in _codes(state)


def test_dangling_price_quantity_is_caught():
    item = BomItem(
        id="b", name="screw", role=BomRole.PART,
        sourcing=Sourcing(supplier="McMaster-Carr", part_number="91290A115",
                          price_quantity_id="q_ghost", grounding=["c_src"]),
    )
    state = _state([item], [], [SUPPLIER_CLAIM])
    assert "DANGLING_REFERENCE" in _codes(state)


# --- abstention: a part without sourcing is fine (honest gap, not a failure) ---

def test_part_without_sourcing_is_allowed():
    item = BomItem(id="b", name="screw", role=BomRole.PART)
    assert gate_gamma(_state([item], [], [])).passed


# --- the string-in-claim helper ----------------------------------------------

def test_text_in_claim_normalizes():
    assert text_in_claim("McMaster-Carr", "buy at  mcmaster-carr  today")
    assert not text_in_claim("Fake Shop", "buy at mcmaster-carr today")
    assert not text_in_claim("", "anything")
