"""Depth-audit / facade-killer for the GATE δ⁺ reality proof (src/gen/reality.py).

This file is the *characterization* sibling of test_reality.py. Where the legacy
suite checks individual branches, this suite is explicitly a facade detector: it
proves that

  (a) the HEADLINE output is genuinely COMPUTED FROM THE INPUTS — the verdict's
      residual/status track the actual numbers and the unit-scale conversion, so a
      hardcoded/canned constant could not pass; and
  (b) the documented fail-loud / abstention paths each fire EXACTLY (the mandatory
      negative battery): every INCONCLUSIVE reason and every gate_delta_plus code.

Per CLAUDE.md §1 ("kein faktischer Output ohne Quelle") and §2 ("Verifikation ist ein
Gate"): the reality verdict must never be asserted by fiat, and the gate must reject
illegitimate inputs while NOT punishing an honest "refuted". Both are pinned below.

Offline, no LLM, stdlib + hypothesis only.  Run:  pytest tests/test_reality_characterization.py
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

def _retrieved_source(url: str = "https://nist.gov/reading") -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=True, support=SourceSupport.SUPPORTS)


def _experiment(
    *,
    predicted_value: float,
    predicted_unit: str = "m",
    tolerance: float = 0.01,
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
    unit: str = "m",
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


# === (a) FACADE-KILLER: the verdict is COMPUTED FROM THE INPUTS ===============

def test_residual_tracks_the_measured_value_not_a_constant() -> None:
    """Sweep the measured value while pinning the prediction. If the residual were a
    canned constant the swept residuals would all be equal; instead each must equal the
    real distance |measured − predicted|, so they form a strictly varying sequence."""
    exp = _experiment(predicted_value=10.0, tolerance=0.0)
    measured = [10.0, 10.5, 11.0, 12.0, 7.5]
    residuals = [evaluate_reality(exp, _measurement(value=v)).residual for v in measured]

    assert residuals == [pytest.approx(abs(v - 10.0)) for v in measured]
    # Distinct inputs (other than the symmetric ±) produce distinct residuals: not canned.
    assert len(set(round(r, 9) for r in residuals)) >= 4


def test_status_flips_as_tolerance_crosses_the_residual() -> None:
    """The driving input `tolerance` genuinely decides the verdict: with a fixed residual
    of 0.5 m, a tolerance below it REFUTES and a tolerance at/above it CORROBORATES — the
    boundary `residual <= tolerance` is consumed, not ignored."""
    meas = _measurement(value=10.5)
    refuted = evaluate_reality(_experiment(predicted_value=10.0, tolerance=0.4), meas)
    at_edge = evaluate_reality(_experiment(predicted_value=10.0, tolerance=0.5), meas)
    corrob = evaluate_reality(_experiment(predicted_value=10.0, tolerance=0.6), meas)

    assert refuted.status is EmpiricalStatus.REFUTED
    assert at_edge.status is EmpiricalStatus.CORROBORATED  # inclusive band
    assert corrob.status is EmpiricalStatus.CORROBORATED


def test_unit_scale_conversion_is_real_same_length_three_units() -> None:
    """The same physical length (1.5 m) expressed in m, cm and mm must yield the SAME
    residual against a 1.5 m prediction — proving the meas_scale/pred_scale conversion
    actually runs. A facade that compared raw magnitudes would see 1.5 vs 150 vs 1500
    and refute two of the three."""
    exp = _experiment(predicted_value=1.5, predicted_unit="m", tolerance=1e-6)
    same_length = {
        "m": evaluate_reality(exp, _measurement(value=1.5, unit="m")),
        "cm": evaluate_reality(exp, _measurement(value=150.0, unit="cm")),
        "mm": evaluate_reality(exp, _measurement(value=1500.0, unit="mm")),
    }
    for unit, verdict in same_length.items():
        assert verdict.status is EmpiricalStatus.CORROBORATED, unit
        assert verdict.residual == pytest.approx(0.0, abs=1e-9), unit


def test_unit_scale_conversion_changes_residual_when_magnitude_differs() -> None:
    """Conversely, a genuinely different length in mm must convert into the predicted unit
    and refute: 1600 mm = 1.6 m vs a 1.5 m prediction -> residual 0.1 m, outside 1e-6."""
    exp = _experiment(predicted_value=1.5, predicted_unit="m", tolerance=1e-6)
    verdict = evaluate_reality(exp, _measurement(value=1600.0, unit="mm"))
    assert verdict.status is EmpiricalStatus.REFUTED
    assert verdict.residual == pytest.approx(0.1, abs=1e-9)
    # detail reports the converted value (1.6 m), not the raw 1600 mm reading.
    assert "1.6 m" in verdict.detail


def test_detail_string_reports_the_computed_numbers() -> None:
    """The human-readable detail is derived from the inputs (measured/predicted/residual/
    tolerance all present), not a fixed template — changing the prediction changes it."""
    a = evaluate_reality(_experiment(predicted_value=2.0, tolerance=0.5),
                         _measurement(value=2.3))
    b = evaluate_reality(_experiment(predicted_value=9.0, tolerance=0.5),
                         _measurement(value=2.3))
    assert "predicted=2" in a.detail and "predicted=9" in b.detail
    assert a.detail != b.detail


# === (b) NEGATIVE BATTERY: every abstention / fail-loud path fires exactly ====

# --- evaluate_reality: the INCONCLUSIVE reasons ------------------------------

def test_inconclusive_dimension_mismatch_is_never_silently_compared() -> None:
    # length vs mass — the Mars-Climate-Orbiter homogeneity guard.
    verdict = evaluate_reality(
        _experiment(predicted_value=1.0, predicted_unit="m", tolerance=1e9),
        _measurement(value=1.0, unit="kg"),
    )
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert verdict.within_tolerance is False
    assert math.isnan(verdict.residual)
    assert "dimension mismatch" in verdict.detail


def test_inconclusive_unparseable_unit_does_not_crash() -> None:
    verdict = evaluate_reality(
        _experiment(predicted_value=1.0, predicted_unit="m", tolerance=0.5),
        _measurement(value=1.0, unit="kg//m"),
    )
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "unparseable unit" in verdict.detail


def test_inconclusive_when_unit_has_no_si_scale() -> None:
    # 'widget' shares its own opaque dimension (homogeneity passes) but has no SI scale.
    verdict = evaluate_reality(
        _experiment(predicted_value=1.0, predicted_unit="widget", tolerance=0.5),
        _measurement(value=1.0, unit="widget"),
    )
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "cannot be scaled" in verdict.detail


def test_inconclusive_no_retrieved_provenance_backstop() -> None:
    # Mutate past the ctor guard: a non-retrieved (fabricated) reading must NOT corroborate.
    meas = _measurement(value=1.0)
    object.__setattr__(meas, "sources", [SourceRef(url_or_id="x", retrieved=False)])
    verdict = evaluate_reality(_experiment(predicted_value=1.0, tolerance=0.5), meas)
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "no retrieved provenance" in verdict.detail


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_inconclusive_non_finite_measured_value(bad: float) -> None:
    meas = _measurement(value=1.0)
    object.__setattr__(meas, "value", bad)  # bypass the finite ctor guard
    verdict = evaluate_reality(_experiment(predicted_value=1.0, tolerance=0.5), meas)
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "non-finite" in verdict.detail


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_inconclusive_non_finite_predicted_value(bad: float) -> None:
    exp = _experiment(predicted_value=1.0, tolerance=0.5)
    object.__setattr__(exp, "predicted_value", bad)
    verdict = evaluate_reality(exp, _measurement(value=1.0))
    assert verdict.status is EmpiricalStatus.INCONCLUSIVE
    assert "non-finite" in verdict.detail


# --- gate_delta_plus: the four codes, the clean pass, and honest refutation --

def test_gate_passes_on_legitimate_inputs() -> None:
    result = gate_delta_plus(
        _experiment(predicted_value=1.0, tolerance=0.5, grounding=["C-1"]),
        _measurement(value=1.0),
        [_claim("C-1")],
    )
    assert result.gate == "delta_plus"
    assert result.passed is True
    assert result.failures == []


def test_gate_does_not_fail_on_an_honest_refutation() -> None:
    """The honest-process contract: a REFUTED verdict is a valid scientific outcome and
    must NOT be turned into a gate failure (only illegitimate INPUTS fail the gate)."""
    exp = _experiment(predicted_value=1.0, tolerance=0.001, grounding=["C-1"])
    meas = _measurement(value=2.0)
    assert evaluate_reality(exp, meas).status is EmpiricalStatus.REFUTED
    assert gate_delta_plus(exp, meas, [_claim("C-1")]).passed is True


def test_gate_grounding_unknown_claim_code_and_claim_id() -> None:
    result = gate_delta_plus(
        _experiment(predicted_value=1.0, tolerance=0.5, grounding=["C-1", "C-MISSING"]),
        _measurement(value=1.0),
        [_claim("C-1")],
    )
    assert result.passed is False
    bad = next(f for f in result.failures if f.code == "GROUNDING_UNKNOWN_CLAIM")
    assert bad.claim_id == "C-MISSING"


def test_gate_experiment_mismatch_code() -> None:
    result = gate_delta_plus(
        _experiment(predicted_value=1.0, tolerance=0.5, eid="EXP-1", grounding=["C-1"]),
        _measurement(value=1.0, experiment_id="EXP-OTHER"),
        [_claim("C-1")],
    )
    assert result.passed is False
    assert "EXPERIMENT_MISMATCH" in [f.code for f in result.failures]


def test_gate_unsourced_measurement_code() -> None:
    meas = _measurement(value=1.0)
    object.__setattr__(meas, "sources", [])  # past the ctor guard -> backstop fires
    result = gate_delta_plus(
        _experiment(predicted_value=1.0, tolerance=0.5, grounding=["C-1"]),
        meas,
        [_claim("C-1")],
    )
    assert result.passed is False
    assert "UNSOURCED_MEASUREMENT" in [f.code for f in result.failures]


def test_gate_dead_measurement_source_code() -> None:
    meas = _measurement(
        value=1.0,
        sources=[_retrieved_source(), SourceRef(url_or_id="dead", retrieved=False)],
    )
    result = gate_delta_plus(
        _experiment(predicted_value=1.0, tolerance=0.5, grounding=["C-1"]),
        meas,
        [_claim("C-1")],
    )
    assert result.passed is False
    assert "DEAD_MEASUREMENT_SOURCE" in [f.code for f in result.failures]


def test_gate_accumulates_independent_failures_not_short_circuited() -> None:
    """All independent defects are reported together — the gate diagnoses the full set
    rather than bailing at the first, so an operator sees everything wrong at once."""
    meas = _measurement(
        value=1.0, experiment_id="EXP-OTHER",
        sources=[_retrieved_source(), SourceRef(url_or_id="dead", retrieved=False)],
    )
    result = gate_delta_plus(
        _experiment(predicted_value=1.0, tolerance=0.5, eid="EXP-1", grounding=["C-MISSING"]),
        meas,
        [_claim("C-1")],
    )
    assert result.passed is False
    assert {f.code for f in result.failures} == {
        "GROUNDING_UNKNOWN_CLAIM",
        "EXPERIMENT_MISMATCH",
        "DEAD_MEASUREMENT_SOURCE",
    }


# === property-based invariants (hold for ALL inputs, not hand-picked) =========

@settings(max_examples=200)
@given(
    predicted=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    measured=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    tolerance=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_property_residual_is_the_distance_and_status_maps_one_to_one(
    predicted: float, measured: float, tolerance: float
) -> None:
    """For a same-unit comparison: residual == |measured − predicted| exactly,
    within_tolerance == (residual <= tolerance), and status is a pure function of that
    boolean. This is the formal statement that the verdict is computed, not asserted."""
    exp = _experiment(predicted_value=predicted, tolerance=tolerance)
    verdict = evaluate_reality(exp, _measurement(value=measured))
    assert verdict.residual == pytest.approx(abs(measured - predicted), abs=1e-9, rel=1e-9)
    assert verdict.within_tolerance == (verdict.residual <= tolerance)
    expected = (
        EmpiricalStatus.CORROBORATED if verdict.within_tolerance else EmpiricalStatus.REFUTED
    )
    assert verdict.status is expected


@settings(max_examples=200)
@given(
    value=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False),
    factor=st.sampled_from([("cm", 100.0), ("mm", 1000.0)]),
)
def test_property_unit_scale_round_trip_corroborates(
    value: float, factor: tuple[str, float]
) -> None:
    """Scaling invariant: a reading of (x·k) in a sub-unit is the SAME length as x m, so it
    must always corroborate against an x m prediction. Tolerance scales with magnitude to
    absorb the few-ULP float error of the conversion (a real check, never tolerance 0)."""
    unit, k = factor
    exp = _experiment(predicted_value=value, predicted_unit="m", tolerance=abs(value) * 1e-6)
    verdict = evaluate_reality(exp, _measurement(value=value * k, unit=unit))
    assert verdict.status is EmpiricalStatus.CORROBORATED


@settings(max_examples=100)
@given(
    predicted=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
    measured=st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
)
def test_property_evaluate_reality_is_deterministic(predicted: float, measured: float) -> None:
    """Reproducibility (A5): identical inputs yield an identical verdict on every call."""
    exp = _experiment(predicted_value=predicted, tolerance=1.0)
    meas = _measurement(value=measured)
    assert evaluate_reality(exp, meas) == evaluate_reality(exp, meas)
