"""Depth-audit characterization tests for the GATE δ-physics aggregator.

These tests exist to KILL the facade hypothesis: that ``gate_delta_physics`` /
``run_physics_checks`` is a hollow stub returning a canned verdict regardless of
input. They prove the gate is a REAL aggregator by driving it with hand-built
``PhysicsCheck`` lists carrying resolved numeric inputs and asserting:

  * the verdict is INPUT-DRIVEN — the same validator passes or fails purely on its
    numeric margin (not on a constant), and
  * every documented fail-loud code fires with its EXACT string
    (``PHYSICS_UNKNOWN_VALIDATOR`` / ``PHYSICS_CHECK_ERROR`` / ``PHYSICS_CHECK_FAILED``),
    upholding "keine stillen Defaults" and "a gate without a test does not exist".

The numeric anchors are the exact closed-form values pinned in the validators'
own docstrings (pressure_vessel: p=10, r=500, t=10 -> hoop=500 MPa; plate_bending
clamped: q=0.1, R=100, t=5, E=210000, nu=0.3 -> sigma~=30 MPa), so a pass/fail flip
proves the validator genuinely ran rather than echoing a stored answer.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from hypothesis import example, given, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.physics_validation import (  # noqa: E402
    VALIDATORS,
    PhysicsCheck,
    gate_delta_physics,
    run_physics_checks,
)


# --- input-driven verdict: the SAME validator passes or fails on its margin ---

def test_pressure_vessel_check_clears_margin_passes():
    """Anchor p=10, r=500, t=10 -> hoop=500 MPa; yield 600 -> SF=1.2 >= 1 -> pass."""
    checks = [
        PhysicsCheck(
            name="tank wall",
            validator="pressure_vessel",
            inputs={
                "pressure": 10.0,
                "r_inner": 500.0,
                "thickness": 10.0,
                "yield_strength": 600.0,
            },
        )
    ]
    result = gate_delta_physics(checks)
    assert result.gate == "delta-physics"
    assert result.passed is True
    assert result.failures == []


def test_pressure_vessel_check_below_margin_fails_with_safety_factor():
    """SAME validator, weaker yield (300 -> SF=0.6 < 1) must fail loud.

    The flip from pass to fail under an input change is the facade-killer: a canned
    verdict could not depend on yield_strength. The PHYSICS_CHECK_FAILED detail must
    carry the computed safety factor as evidence.
    """
    checks = [
        PhysicsCheck(
            name="tank wall",
            validator="pressure_vessel",
            inputs={
                "pressure": 10.0,
                "r_inner": 500.0,
                "thickness": 10.0,
                "yield_strength": 300.0,
            },
        )
    ]
    result = gate_delta_physics(checks)
    assert result.passed is False
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.code == "PHYSICS_CHECK_FAILED"
    assert "tank wall" in failure.detail
    assert "pressure_vessel" in failure.detail
    # SF = 300 / 500 = 0.6 — the actual computed margin, not a placeholder.
    assert "0.6" in failure.detail


def test_second_validator_also_input_driven_plate_bending():
    """A different validator (plate_bending) flips on its allowable stress too.

    Two independent validators both responding to their inputs proves the gate
    dispatches to real code per validator, not a single hardcoded branch.
    """
    base_inputs = {
        "pressure_q": 0.1,
        "radius_R": 100.0,
        "thickness_t": 5.0,
        "e_modulus": 210000.0,
        "nu": 0.3,
    }
    # Anchor max_stress ~= 30 MPa (clamped). Generous allowable clears it; tiny fails.
    passing = gate_delta_physics([
        PhysicsCheck("plate ok", "plate_bending", {**base_inputs, "allowable_stress": 60.0})
    ])
    failing = gate_delta_physics([
        PhysicsCheck("plate weak", "plate_bending", {**base_inputs, "allowable_stress": 15.0})
    ])
    assert passing.passed is True
    assert failing.passed is False
    assert failing.failures[0].code == "PHYSICS_CHECK_FAILED"


# --- all three documented fail-loud codes fire with EXACT strings ---

def test_unknown_validator_fires_exact_code():
    checks = [PhysicsCheck("mystery", "no_such_validator", {})]
    result = gate_delta_physics(checks)
    assert result.passed is False
    assert len(result.failures) == 1
    assert result.failures[0].code == "PHYSICS_UNKNOWN_VALIDATOR"
    assert "mystery" in result.failures[0].detail


def test_validator_that_raises_fires_check_error():
    """A contradictory geometry (non-positive radius) makes pressure_vessel raise.

    The gate must surface this as PHYSICS_CHECK_ERROR — never swallow it into a
    silent pass.
    """
    checks = [
        PhysicsCheck(
            name="bad tank",
            validator="pressure_vessel",
            inputs={
                "pressure": 10.0,
                "r_inner": -1.0,  # non-positive -> GeometryError inside the validator
                "thickness": 10.0,
                "yield_strength": 600.0,
            },
        )
    ]
    result = gate_delta_physics(checks)
    assert result.passed is False
    assert len(result.failures) == 1
    assert result.failures[0].code == "PHYSICS_CHECK_ERROR"
    assert "bad tank" in result.failures[0].detail
    assert "pressure_vessel" in result.failures[0].detail


def test_empty_check_list_passes_vacuously():
    result = gate_delta_physics([])
    assert result.passed is True
    assert result.failures == []


# --- mixed batch: one bad check does not abort the rest; codes are per-check ---

def test_mixed_batch_collects_every_failure_independently():
    """run_physics_checks runs each validator in isolation: a raising check, an
    unknown check and a failing check all produce their own distinct verdict, and a
    good check still reports ok=True alongside them.
    """
    checks = [
        PhysicsCheck("good", "pressure_vessel", {
            "pressure": 10.0, "r_inner": 500.0, "thickness": 10.0, "yield_strength": 600.0,
        }),
        PhysicsCheck("unknown", "not_a_validator", {}),
        PhysicsCheck("error", "pressure_vessel", {
            "pressure": 10.0, "r_inner": -1.0, "thickness": 10.0, "yield_strength": 600.0,
        }),
        PhysicsCheck("failed", "pressure_vessel", {
            "pressure": 10.0, "r_inner": 500.0, "thickness": 10.0, "yield_strength": 300.0,
        }),
    ]
    evidence = run_physics_checks(checks)
    statuses = {e["name"]: e["status"] for e in evidence}
    assert statuses == {
        "good": "ran", "unknown": "unknown", "error": "error", "failed": "ran",
    }
    assert evidence[0]["ok"] is True
    assert evidence[3]["ok"] is False

    result = gate_delta_physics(checks)
    codes = sorted(f.code for f in result.failures)
    assert codes == [
        "PHYSICS_CHECK_ERROR", "PHYSICS_CHECK_FAILED", "PHYSICS_UNKNOWN_VALIDATOR",
    ]


# --- registry integrity: not a single stale / non-callable key ---

def test_validators_registry_all_callable():
    """A registry key bound to a renamed/missing function would silently degrade the
    gate (every check naming it would become PHYSICS_UNKNOWN_VALIDATOR at runtime).
    """
    assert VALIDATORS, "registry must not be empty"
    for name, fn in VALIDATORS.items():
        assert callable(fn), f"validator {name!r} is not callable: {fn!r}"


def test_run_physics_checks_evidence_shape():
    """Every evidence dict carries the documented keys for downstream rendering."""
    evidence = run_physics_checks([
        PhysicsCheck("p", "pressure_vessel", {
            "pressure": 10.0, "r_inner": 500.0, "thickness": 10.0, "yield_strength": 600.0,
        })
    ])
    assert set(evidence[0]) == {"name", "validator", "status", "ok", "detail", "result"}


# --- property: pass/fail is monotone in the safety margin (yield strength) ---

# The SF == 1.0 boundary is the most error-prone point of the `>=` predicate, so pin
# it explicitly: r_inner=500, thickness=10, pressure=10 -> hoop=500; yield=500 -> SF=1.0.
@example(yield_strength=500.0, pressure=10.0)
@given(
    yield_strength=st.floats(min_value=1.0, max_value=5000.0),
    pressure=st.floats(min_value=0.1, max_value=50.0),
)
def test_property_pass_iff_safety_factor_at_least_one(yield_strength, pressure):
    """INVARIANT: the gate passes a single pressure_vessel check exactly when the
    closed-form safety factor (yield / hoop, hoop = p*r/t) is >= 1. This pins the
    verdict to real arithmetic for all inputs, not a hand-picked pair.
    """
    r_inner, thickness = 500.0, 10.0
    hoop = pressure * r_inner / thickness
    expected_pass = (yield_strength / hoop) >= 1.0
    result = gate_delta_physics([
        PhysicsCheck("p", "pressure_vessel", {
            "pressure": pressure, "r_inner": r_inner,
            "thickness": thickness, "yield_strength": yield_strength,
        })
    ])
    assert result.passed is expected_pass
    # When it passes there are zero failures; when it fails there is exactly the
    # PHYSICS_CHECK_FAILED one — no spurious extra codes.
    if expected_pass:
        assert result.failures == []
    else:
        assert [f.code for f in result.failures] == ["PHYSICS_CHECK_FAILED"]


def test_property_helper_no_floating_point_surprise_at_anchor():
    """Guard the exact anchor stays exact (hoop=500 is representable)."""
    assert math.isclose(10.0 * 500.0 / 10.0, 500.0)
