"""Depth-audit (characterization) for printability.py — the FDM design-rule validators.

This is a FACADE-DETECTOR, distinct from the legacy tests/test_printability.py.
For every one of the seven validators it asserts the two things that separate a real
closed-form check from a canned constant:

  (a) the headline output (safety_factor / ok / derived limit) changes MEANINGFULLY
      when a DRIVING input changes — proving the input is genuinely consumed, not
      echoed back from a hard-coded value; and
  (b) EVERY documented ValueError / abstention path fires exactly — proving the
      fail-loud guards exist ("ein Gate ohne Test existiert nicht").

Property-based tests (Hypothesis) pin the closed-form invariants that hold for ALL
valid inputs: safety_factor == quantity / limit, ok ⇔ safety_factor >= 1 at the
limit, and monotonicity in the driving input.

Offline, no LLM, no numpy. Run:  pytest tests/test_printability_characterization.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, strategies as st  # noqa: E402

from gen.printability import (  # noqa: E402
    FDM_CLEARANCE_LOOSE_MM,
    FDM_CLEARANCE_TIGHT_MM,
    FDM_MAX_BRIDGE_MM,
    FDM_MIN_EMBOSS_WIDTH_MM,
    FDM_MIN_ENGRAVE_WIDTH_MM,
    FDM_MIN_PIN_DIAMETER_MM,
    FDM_MIN_THREAD_MAJOR_MM,
    FDM_MIN_UNSUPPORTED_WALL_MM,
    FDM_PIN_FILLET_BELOW_MM,
    FDM_Z_STRENGTH_RETENTION,
    bridge_span_check,
    emboss_detail_check,
    fdm_fit_clearance_check,
    layer_adhesion_check,
    pin_diameter_check,
    thread_size_check,
    unsupported_wall_check,
)

# Strategy for "ordinary" finite positive lengths the validators are designed for.
# Bounded away from 0 and from huge values so safety-factor ratios stay finite and
# the closed-form comparisons are not swamped by float error.
_LENGTHS = st.floats(min_value=1e-3, max_value=1e4, allow_nan=False, allow_infinity=False)


# ============================================================== bridge_span_check
def test_bridge_safety_factor_is_driven_by_span_not_canned():
    # Facade-killer (a): doubling the span must HALVE the safety factor.
    # If safety_factor were a constant, both calls would be equal.
    near = bridge_span_check(5.0)["safety_factor"]
    far = bridge_span_check(10.0)["safety_factor"]
    assert near == pytest.approx(2.0 * far)
    # And the custom max_span argument must actually flow through (not ignored).
    custom = bridge_span_check(5.0, max_span=20.0)["safety_factor"]
    assert custom == pytest.approx(4.0)
    assert custom != near  # the second driving input genuinely moved the output


def test_bridge_zero_span_abstains_with_inf():
    assert bridge_span_check(0.0)["safety_factor"] == math.inf
    assert bridge_span_check(FDM_MAX_BRIDGE_MM)["ok"]  # limit is inclusive


def test_bridge_negative_span_and_nonpositive_limit_raise():
    with pytest.raises(ValueError):
        bridge_span_check(-0.5)
    with pytest.raises(ValueError):
        bridge_span_check(5.0, max_span=0.0)
    with pytest.raises(ValueError):
        bridge_span_check(5.0, max_span=-3.0)


@given(span=st.floats(min_value=1e-6, max_value=1e4, allow_nan=False), max_span=_LENGTHS)
def test_bridge_safety_factor_invariant(span, max_span):
    r = bridge_span_check(span, max_span=max_span)
    assert r["safety_factor"] == pytest.approx(max_span / span)
    # ok is exactly equivalent to "at or under the limit".
    assert r["ok"] == (span <= max_span)


# ========================================================= fdm_fit_clearance_check
def test_clearance_floor_switches_with_fit_kind():
    # Facade-killer (a): the SAME clearance gives different verdicts depending on
    # the fit, which is only possible if `fit` selects a real floor.
    loose = fdm_fit_clearance_check(0.15, fit="loose")
    tight = fdm_fit_clearance_check(0.15, fit="tight")
    assert loose["floor"] == FDM_CLEARANCE_LOOSE_MM
    assert tight["floor"] == FDM_CLEARANCE_TIGHT_MM
    assert not loose["ok"] and tight["ok"]  # 0.15 jams a loose fit, clears a tight one
    # safety_factor tracks the chosen floor, not a constant.
    assert loose["safety_factor"] == pytest.approx(0.15 / FDM_CLEARANCE_LOOSE_MM)
    assert tight["safety_factor"] == pytest.approx(0.15 / FDM_CLEARANCE_TIGHT_MM)


def test_clearance_interference_fails_without_raising():
    # A negative (interference) clearance is meaningful input: it fails, it does not raise.
    r = fdm_fit_clearance_check(-0.05)
    assert not r["ok"] and r["safety_factor"] < 0.0


def test_clearance_unknown_fit_raises():
    with pytest.raises(ValueError):
        fdm_fit_clearance_check(0.3, fit="press")


@given(clearance=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
       fit=st.sampled_from(["loose", "tight"]))
def test_clearance_safety_factor_invariant(clearance, fit):
    r = fdm_fit_clearance_check(clearance, fit=fit)
    assert r["safety_factor"] == pytest.approx(clearance / r["floor"])
    assert r["ok"] == (clearance >= r["floor"])


# ============================================================== pin_diameter_check
def test_pin_safety_factor_and_fillet_flag_track_diameter():
    # Facade-killer (a): safety_factor scales with diameter; fillet flag flips at 5 mm.
    r4 = pin_diameter_check(4.0)
    r6 = pin_diameter_check(6.0)
    assert r6["safety_factor"] == pytest.approx(1.5 * r4["safety_factor"])
    assert r4["fillet_recommended"] and not r6["fillet_recommended"]
    # The custom min_diameter argument must flow through.
    assert pin_diameter_check(4.0, min_diameter=2.0)["safety_factor"] == pytest.approx(2.0)


def test_pin_fillet_threshold_is_exclusive_at_5mm():
    # < 5 mm recommends a fillet; exactly 5 mm does not (documented "below 5 mm").
    assert pin_diameter_check(FDM_PIN_FILLET_BELOW_MM)["fillet_recommended"] is False
    assert pin_diameter_check(FDM_PIN_FILLET_BELOW_MM - 1e-9)["fillet_recommended"] is True


def test_pin_nonpositive_inputs_raise():
    with pytest.raises(ValueError):
        pin_diameter_check(0.0)
    with pytest.raises(ValueError):
        pin_diameter_check(-2.0)
    with pytest.raises(ValueError):
        pin_diameter_check(3.0, min_diameter=0.0)


@given(diameter=_LENGTHS)
def test_pin_safety_factor_invariant(diameter):
    r = pin_diameter_check(diameter)
    assert r["safety_factor"] == pytest.approx(diameter / FDM_MIN_PIN_DIAMETER_MM)
    assert r["ok"] == (diameter >= FDM_MIN_PIN_DIAMETER_MM)


# =============================================================== thread_size_check
def test_thread_verdict_and_insert_flag_track_major_diameter():
    m6 = thread_size_check(6.0)
    m3 = thread_size_check(3.0)
    assert m6["ok"] and not m6["use_insert_or_tap"]
    assert not m3["ok"] and m3["use_insert_or_tap"]  # honest alternative below M5
    # safety_factor genuinely scales with the major diameter.
    assert m6["safety_factor"] == pytest.approx(2.0 * thread_size_check(3.0)["safety_factor"])


def test_thread_nonpositive_inputs_raise():
    with pytest.raises(ValueError):
        thread_size_check(-2.0)
    with pytest.raises(ValueError):
        thread_size_check(6.0, min_major=0.0)


@given(major=_LENGTHS)
def test_thread_use_insert_is_exact_negation_of_ok(major):
    r = thread_size_check(major)
    # use_insert_or_tap must be the exact complement of ok — never both, never neither.
    assert r["use_insert_or_tap"] == (not r["ok"])
    assert r["ok"] == (major >= FDM_MIN_THREAD_MAJOR_MM)


# =========================================================== unsupported_wall_check
def test_wall_safety_factor_is_driven_by_thickness():
    thin = unsupported_wall_check(0.5)
    thick = unsupported_wall_check(1.5)
    assert thick["safety_factor"] == pytest.approx(3.0 * thin["safety_factor"])
    assert not thin["ok"] and thick["ok"]
    # 0.9 mm passes the supported-wall DFM floor (0.8) yet fails free-standing (1.0).
    assert not unsupported_wall_check(0.9)["ok"]


def test_wall_nonpositive_inputs_raise():
    with pytest.raises(ValueError):
        unsupported_wall_check(0.0)
    with pytest.raises(ValueError):
        unsupported_wall_check(1.0, min_thickness=-0.5)


@given(thickness=_LENGTHS)
def test_wall_safety_factor_invariant(thickness):
    r = unsupported_wall_check(thickness)
    assert r["safety_factor"] == pytest.approx(thickness / FDM_MIN_UNSUPPORTED_WALL_MM)
    assert r["ok"] == (thickness >= FDM_MIN_UNSUPPORTED_WALL_MM)


# ============================================================== emboss_detail_check
def test_detail_floor_switches_with_kind():
    # Facade-killer (a): the SAME width gives different verdicts for emboss vs engrave.
    w = 0.6
    raised = emboss_detail_check(w, kind="emboss")
    recessed = emboss_detail_check(w, kind="engrave")
    assert raised["min_width"] == FDM_MIN_EMBOSS_WIDTH_MM
    assert recessed["min_width"] == FDM_MIN_ENGRAVE_WIDTH_MM
    assert not raised["ok"] and recessed["ok"]  # 0.6 fuses raised, but is fine recessed
    assert raised["safety_factor"] == pytest.approx(w / FDM_MIN_EMBOSS_WIDTH_MM)


def test_detail_unknown_kind_and_nonpositive_width_raise():
    with pytest.raises(ValueError):
        emboss_detail_check(1.0, kind="deboss")
    with pytest.raises(ValueError):
        emboss_detail_check(0.0)
    with pytest.raises(ValueError):
        emboss_detail_check(-0.5, kind="engrave")


@given(width=_LENGTHS, kind=st.sampled_from(["emboss", "engrave"]))
def test_detail_safety_factor_invariant(width, kind):
    r = emboss_detail_check(width, kind=kind)
    assert r["safety_factor"] == pytest.approx(width / r["min_width"])
    assert r["ok"] == (width >= r["min_width"])


# ============================================================= layer_adhesion_check
def test_adhesion_uses_retained_strength_not_quoted():
    # Facade-killer (a): allowed_stress must DERIVE from base_strength * z_retention,
    # not be a constant — so it scales with both drivers.
    r = layer_adhesion_check(10.0, 50.0)
    assert r["allowed_stress"] == pytest.approx(FDM_Z_STRENGTH_RETENTION * 50.0)
    assert r["safety_factor"] == pytest.approx(r["allowed_stress"] / 10.0)
    # Doubling base strength doubles the allowance; a custom retention flows through.
    assert layer_adhesion_check(10.0, 100.0)["allowed_stress"] == pytest.approx(
        2.0 * r["allowed_stress"]
    )
    assert layer_adhesion_check(10.0, 50.0, z_retention=0.9)["allowed_stress"] == pytest.approx(
        0.9 * 50.0
    )
    # A stress that passes the QUOTED strength still fails the RETAINED strength —
    # the failure a print reveals and the CAD hides.
    assert not layer_adhesion_check(30.0, 50.0)["ok"]


def test_adhesion_zero_stress_abstains_with_inf():
    r = layer_adhesion_check(0.0, 50.0)
    assert r["safety_factor"] == math.inf and r["ok"]
    assert r["z_retention"] == FDM_Z_STRENGTH_RETENTION


def test_adhesion_rejects_signed_stress_and_bad_params():
    with pytest.raises(ValueError):  # compression does not delaminate
        layer_adhesion_check(-5.0, 50.0)
    with pytest.raises(ValueError):
        layer_adhesion_check(10.0, 0.0)
    with pytest.raises(ValueError):  # retention must be in (0, 1]
        layer_adhesion_check(10.0, 50.0, z_retention=1.2)
    with pytest.raises(ValueError):
        layer_adhesion_check(10.0, 50.0, z_retention=0.0)


@given(
    stress=st.floats(min_value=1e-6, max_value=1e4, allow_nan=False),
    base=st.floats(min_value=1e-3, max_value=1e4, allow_nan=False),
    retention=st.floats(min_value=1e-3, max_value=1.0, allow_nan=False),
)
def test_adhesion_safety_factor_invariant(stress, base, retention):
    r = layer_adhesion_check(stress, base, z_retention=retention)
    allowed = retention * base
    assert r["allowed_stress"] == pytest.approx(allowed)
    assert r["safety_factor"] == pytest.approx(allowed / stress)
    assert r["ok"] == (r["safety_factor"] >= 1.0)
