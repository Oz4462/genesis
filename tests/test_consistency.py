"""GATE γ C-17 — cross-claim consistency over declared measurands.

GENESIS already proves each claim sound in isolation (sourced, verified, not
refuted). It did NOT, until now, catch a contradiction BETWEEN two accepted,
claim-grounded facts: one grounding claim could say the LED strip runs at 12 V
and another (cited elsewhere) at 24 V, and both passed.

C-17 closes that hole deterministically. Two quantities tagged with the same
declared `measurand` claim to measure the same physical quantity, so they must
agree — same dimension AND the same value after unit conversion. The link is
DECLARED (the measurand tag, made explicit by the architect), the conflict is
pure arithmetic + dimensions — no language understanding, and no false positive
(a conflict is raised only when the values are provably unequal). A unit-only
difference (12 V vs 0.012 kV) is NOT a conflict.

Offline, no LLM, no network.

Run:  pytest tests/test_consistency.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.core.errors import InvalidDerivationError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    Question,
    Quantity,
    RunState,
    SourceRef,
    SourceSupport,
    Specification,
    ValueOrigin,
)
from gen.verification.gates import gate_gamma  # noqa: E402


def _claim(cid: str, text: str) -> Claim:
    return Claim(
        id=cid, text=text,
        sources=[SourceRef(f"https://{cid}", True, support=SourceSupport.SUPPORTS)],
        status=ClaimStatus.VERIFIED, confidence=0.95,
        verification=[SourceRef(f"https://i/{cid}", True, support=SourceSupport.SUPPORTS)],
    )


def _grounded(qid: str, value: float, unit: str, claim_id: str, measurand: str) -> Quantity:
    return Quantity(id=qid, name=qid, value=value, unit=unit,
                    origin=ValueOrigin.GROUNDED, grounding=[claim_id], measurand=measurand)


def _state(*quantities: Quantity, claims) -> RunState:
    spec = Specification(run_id="r", idea="consistency", quantities=list(quantities))
    st = RunState(question=Question(raw="c", run_id="r"))
    st.claims = claims
    st.specification = spec
    return st


# --- the conflict is caught ----------------------------------------------------

def test_contradicting_grounded_values_for_one_measurand_are_caught():
    st = _state(
        _grounded("q_v_a", 12.0, "V", "c_a", "led_strip.voltage"),
        _grounded("q_v_b", 24.0, "V", "c_b", "led_strip.voltage"),
        claims=[
            _claim("c_a", "The LED strip runs at 12 V."),
            _claim("c_b", "The LED strip runs at 24 V."),
        ],
    )
    codes = {f.code for f in gate_gamma(st).failures}
    assert "CROSS_CLAIM_CONFLICT" in codes


def test_same_measurand_incompatible_dimensions_is_a_conflict():
    # one claim measures it as a voltage, another as a length — cannot both be true
    st = _state(
        _grounded("q_a", 12.0, "V", "c_a", "thing.x"),
        _grounded("q_b", 12.0, "mm", "c_b", "thing.x"),
        claims=[_claim("c_a", "x is 12 V."), _claim("c_b", "x is 12 mm.")],
    )
    codes = {f.code for f in gate_gamma(st).failures}
    assert "CROSS_CLAIM_CONFLICT" in codes


# --- agreement passes (no false positive) --------------------------------------

def test_agreeing_values_pass():
    st = _state(
        _grounded("q_v_a", 12.0, "V", "c_a", "led_strip.voltage"),
        _grounded("q_v_b", 12.0, "V", "c_b", "led_strip.voltage"),
        claims=[
            _claim("c_a", "The LED strip runs at 12 V."),
            _claim("c_b", "Its supply rail is 12 V."),
        ],
    )
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_unit_only_difference_is_not_a_conflict():
    # 12 V and 0.012 kV are the SAME voltage — conversion-aware, no false positive
    st = _state(
        _grounded("q_v_a", 12.0, "V", "c_a", "led_strip.voltage"),
        _grounded("q_v_b", 0.012, "kV", "c_b", "led_strip.voltage"),
        claims=[
            _claim("c_a", "The LED strip runs at 12 V."),
            _claim("c_b", "The strip rail is 0.012 kV."),
        ],
    )
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_distinct_measurands_do_not_interfere():
    # different things at different voltages is perfectly fine
    st = _state(
        _grounded("q_led", 12.0, "V", "c_a", "led_strip.voltage"),
        _grounded("q_mcu", 3.3, "V", "c_b", "mcu.voltage"),
        claims=[_claim("c_a", "The LED strip runs at 12 V."),
                _claim("c_b", "The MCU runs at 3.3 V.")],
    )
    result = gate_gamma(st)
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


def test_untagged_quantities_are_unaffected():
    # the whole capstone has no measurand tags -> C-17 never fires there
    from gen.demo import capstone_state
    result = gate_gamma(capstone_state())
    assert result.passed, [f"{f.code}: {f.detail}" for f in result.failures]


# --- the tag itself must be honest ---------------------------------------------

def test_blank_measurand_is_rejected_at_construction():
    with pytest.raises(InvalidDerivationError):
        Quantity(id="q", name="q", value=1.0, unit="V",
                 origin=ValueOrigin.DECISION, rationale="x", measurand="   ")
