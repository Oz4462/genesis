"""Unit tests for the GATE δ⁺ reality proof (src/gen/reality.py).

These exercise `evaluate_reality` (the deterministic measured-vs-predicted verdict,
dimension-safe) and `gate_delta_plus` (the honest-process gate over the inputs) in
isolation — the phase-acceptance integration tests only hit them incidentally.

Covered per the task spec:
  * unit-scaled comparison (predicted in 'm', measurement in 'mm');
  * the CORROBORATED / REFUTED / INCONCLUSIVE branches and the <=-tolerance boundary;
  * the dimensional-homogeneity guard (different dimensions never compared);
  * the no-retrieved-provenance and non-finite backstops (defense-in-depth, reached
    by mutating a frozen dataclass past its own constructor guard);
  * every `gate_delta_plus` failure code (GROUNDING_UNKNOWN_CLAIM, EXPERIMENT_MISMATCH,
    UNSOURCED_MEASUREMENT, DEAD_MEASUREMENT_SOURCE) plus the clean pass.

Offline, no LLM, stdlib + hypothesis only. Run:  pytest tests/test_reality.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    EmpiricalStatus,
    FalsificationExperiment,
    Measurement,
    SourceRef,
    SourceSupport,
)
from gen.reality import evaluate_reality, gate_delta_plus  # noqa: E402


# --- builders ----------------------------------------------------------------
# Tiny grounded constructors so each test reads as one comparison, not boilerplate.

def _retrieved_source(url: str = "https://nist.gov/reading") -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=True, support=SourceSupport.SUPPORTS)


def _experiment(
    *,
    predicted_value: float,
    predicted_unit: str,
    tolerance: float,
    eid: str = "EXP-1",
    grounding: list[str] | None = None,
) -> FalsificationExperiment:
    return FalsificationExperiment(
        id=eid,
        measurand="length",
        predicted_value=predicted_value,
        predicted_unit=predicted_unit,
        tolerance=tolerance,
        method="measure it",
        grounding=grounding if grounding is not None else ["C-1"],
    )


def _measurement(
    *,
    value: float,
    unit: str,
    experiment_id: str = "EXP-1",
    sources: list[SourceRef] | None = None,
    mid: str = "M-1",
) -> Measurement:
    return Measurement(
        id=mid,
        experiment_id=experiment_id,
        value=value,
        unit=unit,
        sources=sources if sources is not None else [_retrieved_source()],
    )


def _claim(cid: str = "C-1") -> Claim:
    return Claim(
        id=cid,
        text="the bar is one metre long",
        sources=[_retrieved_source()],
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
    )


# --- evaluate_reality: the three verdict branches ----------------------------

def test_corroborated_same_unit_within_tolerance() -> None:
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.01)
    verdict = evaluate_reality(exp, _measurement(value=1.005, unit="m"))
    assert verdict.status is EmpiricalStatus.CORROBORATED
    assert verdict.within_tolerance is True
    # residual is the absolute distance in the predicted unit.
    assert verdict.residual == pytest.approx(0.005)


def test_refuted_same_unit_outside_tolerance() -> None:
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.01)
    verdict = evaluate_reality(exp, _measurement(value=1.5, unit="m"))
    assert verdict.status is EmpiricalStatus.REFUTED
    assert verdict.within_tolerance is False
    assert verdict.residual == pytest.approx(0.5)


def test_tolerance_boundary_is_inclusive() -> None:
    # CORROBORATED uses |measured - predicted| <= tolerance, so residual == tolerance
    # must corroborate (closed band); a hair beyond must refute.
    exp = _experiment(predicted_value=10.0, predicted_unit="m", tolerance=1.0)
    at_edge = evaluate_reality(exp, _measurement(value=11.0, unit="m"))
    assert at_edge.status is EmpiricalStatus.CORROBORATED
    assert at_edge.residual == pytest.approx(1.0)

    just_outside = evaluate_reality(exp, _measurement(value=11.0001, unit="m"))
    assert just_outside.status is EmpiricalStatus.REFUTED


# --- evaluate_reality: unit-scaled comparison --------------------------------

def test_unit_scaled_comparison_metre_vs_millimetre_corroborated() -> None:
    # Predicted 1.0 m; measured 1005 mm = 1.005 m -> residual 0.005 m <= 0.01 m.
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.01)
    verdict = evaluate_reality(exp, _measurement(value=1005.0, unit="mm"))
    assert verdict.status is EmpiricalStatus.CORROBORATED
    assert verdict.residual == pytest.approx(0.005, abs=1e-9)
    # The detail reports the value converted INTO the predicted unit, not the raw mm.
    assert "m," in verdict.detail


def test_unit_scaled_comparison_metre_vs_millimetre_refuted() -> None:
    # Measured 1100 mm = 1.1 m -> residual 0.1 m > 0.01 m.
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.01)
    verdict = evaluate_reality(exp, _measurement(value=1100.0, unit="mm"))
    assert verdict.status is EmpiricalStatus.REFUTED
    assert verdict.residual == pytest.approx(0.1, abs=1e-9)


# --- evaluate_reality: INCONCLUSIVE branches ---------------------------------

def test_inconclusive_on_dimension_mismatch_homogeneity_guard() -> None:
    # length vs mass — incommensurable; must never be silently compared.
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5)
    verdict = evaluate_reality(exp, _measurement(value=1.0, unit="kg"))
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert verdict.within_tolerance is False
    assert math.isnan(verdict.residual)
    assert "dimension mismatch" in verdict.detail


def test_inconclusive_on_unparseable_unit() -> None:
    # "kg//m" violates the unit grammar -> parse_unit raises -> INCONCLUSIVE, not a crash.
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5)
    verdict = evaluate_reality(exp, _measurement(value=1.0, unit="kg//m"))
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert math.isnan(verdict.residual)
    assert "unparseable unit" in verdict.detail


def test_inconclusive_when_unit_has_no_si_scale() -> None:
    # An opaque atom shares its own dimension with itself (so the homogeneity check
    # passes) but has no sound SI scale -> GENESIS refuses to compare magnitudes.
    exp = _experiment(predicted_value=1.0, predicted_unit="widget", tolerance=0.5)
    verdict = evaluate_reality(exp, _measurement(value=1.0, unit="widget"))
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert math.isnan(verdict.residual)
    assert "cannot be scaled" in verdict.detail


# --- evaluate_reality: defense-in-depth backstops ----------------------------
# The constructors already forbid these, so we mutate the frozen dataclass past its
# guard to prove reality.py independently refuses to corroborate from bad evidence.

def test_backstop_no_retrieved_provenance() -> None:
    meas = _measurement(value=1.0, unit="m")
    # Strip provenance to a non-retrieved (fabricated) reading, bypassing the ctor guard.
    object.__setattr__(meas, "sources", [SourceRef(url_or_id="x", retrieved=False)])
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5)
    verdict = evaluate_reality(exp, meas)
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "no retrieved provenance" in verdict.detail


def test_backstop_no_sources_at_all() -> None:
    meas = _measurement(value=1.0, unit="m")
    object.__setattr__(meas, "sources", [])  # empty -> any(...) is False
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5)
    verdict = evaluate_reality(exp, meas)
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "no retrieved provenance" in verdict.detail


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_backstop_non_finite_measured_value(bad: float) -> None:
    meas = _measurement(value=1.0, unit="m")
    object.__setattr__(meas, "value", bad)
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5)
    verdict = evaluate_reality(exp, meas)
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "non-finite" in verdict.detail


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_backstop_non_finite_predicted_value(bad: float) -> None:
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5)
    object.__setattr__(exp, "predicted_value", bad)
    verdict = evaluate_reality(exp, _measurement(value=1.0, unit="m"))
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "non-finite" in verdict.detail


# --- gate_delta_plus: the four failure codes + clean pass --------------------

def test_gate_passes_on_legitimate_inputs() -> None:
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5,
                      grounding=["C-1"])
    result = gate_delta_plus(exp, _measurement(value=1.0, unit="m"), [_claim("C-1")])
    assert result.gate == "delta_plus"
    assert result.passed is True
    assert result.failures == []


def test_gate_passes_even_when_verdict_is_refuted() -> None:
    # An honest "widerlegt" is a valid outcome, NOT an illegitimate input -> gate passes.
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.001,
                      grounding=["C-1"])
    meas = _measurement(value=2.0, unit="m")
    assert evaluate_reality(exp, meas).status is EmpiricalStatus.REFUTED
    assert gate_delta_plus(exp, meas, [_claim("C-1")]).passed is True


def test_gate_grounding_unknown_claim() -> None:
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5,
                      grounding=["C-1", "C-MISSING"])
    result = gate_delta_plus(exp, _measurement(value=1.0, unit="m"), [_claim("C-1")])
    assert result.passed is False
    codes = [f.code for f in result.failures]
    assert "GROUNDING_UNKNOWN_CLAIM" in codes
    missing = next(f for f in result.failures if f.code == "GROUNDING_UNKNOWN_CLAIM")
    assert missing.claim_id == "C-MISSING"


def test_gate_experiment_mismatch() -> None:
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5,
                      eid="EXP-1", grounding=["C-1"])
    meas = _measurement(value=1.0, unit="m", experiment_id="EXP-OTHER")
    result = gate_delta_plus(exp, meas, [_claim("C-1")])
    assert result.passed is False
    assert "EXPERIMENT_MISMATCH" in [f.code for f in result.failures]


def test_gate_unsourced_measurement() -> None:
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5,
                      grounding=["C-1"])
    meas = _measurement(value=1.0, unit="m")
    object.__setattr__(meas, "sources", [])  # past the ctor guard
    result = gate_delta_plus(exp, meas, [_claim("C-1")])
    assert result.passed is False
    assert "UNSOURCED_MEASUREMENT" in [f.code for f in result.failures]


def test_gate_dead_measurement_source() -> None:
    # A measurement may carry several sources; ANY non-retrieved one is a dead citation.
    # Constructible directly: one retrieved source satisfies the ctor, the dead one trips
    # the gate.
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5,
                      grounding=["C-1"])
    meas = _measurement(
        value=1.0,
        unit="m",
        sources=[_retrieved_source(), SourceRef(url_or_id="dead", retrieved=False)],
    )
    result = gate_delta_plus(exp, meas, [_claim("C-1")])
    assert result.passed is False
    assert "DEAD_MEASUREMENT_SOURCE" in [f.code for f in result.failures]


def test_gate_accumulates_multiple_failures() -> None:
    # All independent defects are reported together, not short-circuited at the first.
    exp = _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5,
                      eid="EXP-1", grounding=["C-MISSING"])
    meas = _measurement(
        value=1.0, unit="m", experiment_id="EXP-OTHER",
        sources=[_retrieved_source(), SourceRef(url_or_id="dead", retrieved=False)],
    )
    result = gate_delta_plus(exp, meas, [_claim("C-1")])
    codes = {f.code for f in result.failures}
    assert codes == {
        "GROUNDING_UNKNOWN_CLAIM",
        "EXPERIMENT_MISMATCH",
        "DEAD_MEASUREMENT_SOURCE",
    }
    assert result.passed is False


# --- property-based invariants -----------------------------------------------

@settings(max_examples=200)
@given(
    predicted=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    measured=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    tolerance=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_property_residual_and_status_are_consistent(
    predicted: float, measured: float, tolerance: float
) -> None:
    """Core invariant: for a same-unit comparison the residual is exactly the absolute
    distance, within_tolerance is exactly (residual <= tolerance), and the status maps
    one-to-one to that boolean. Holds for every finite triple, not just hand-picked ones.
    """
    exp = _experiment(predicted_value=predicted, predicted_unit="m", tolerance=tolerance)
    verdict = evaluate_reality(exp, _measurement(value=measured, unit="m"))
    assert verdict.residual == pytest.approx(abs(measured - predicted), abs=1e-9, rel=1e-9)
    assert verdict.within_tolerance == (verdict.residual <= tolerance)
    expected = (
        EmpiricalStatus.CORROBORATED if verdict.within_tolerance else EmpiricalStatus.REFUTED
    )
    assert verdict.status is expected


@settings(max_examples=200)
@given(value=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False))
def test_property_metre_millimetre_round_trip_corroborates(value: float) -> None:
    """Unit-scaling invariant: a measurement of (x·1000) mm is the same physical length as
    a prediction of x m, so it must always corroborate. Tolerance scales with magnitude to
    absorb the few-ULP float error of the mm->m conversion (a real magnitude check, not 0).
    """
    exp = _experiment(predicted_value=value, predicted_unit="m", tolerance=abs(value) * 1e-6)
    verdict = evaluate_reality(exp, _measurement(value=value * 1000.0, unit="mm"))
    assert verdict.status is EmpiricalStatus.CORROBORATED


@settings(max_examples=100)
@given(
    predicted=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
    measured=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
)
def test_property_evaluate_reality_is_deterministic(predicted: float, measured: float) -> None:
    """Reproducibility (A5): identical inputs yield an identical verdict every call."""
    exp = _experiment(predicted_value=predicted, predicted_unit="m", tolerance=1.0)
    meas = _measurement(value=measured, unit="m")
    assert evaluate_reality(exp, meas) == evaluate_reality(exp, meas)
