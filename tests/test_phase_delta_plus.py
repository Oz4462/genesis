"""Phase δ⁺ acceptance — the reality proof (HORIZON.md §2B). Deterministic, LLM-free.

Teeth: a measurement without provenance / an experiment without a prediction is impossible
(constructors); the verdict is computed dimension-safe (corroborated within tolerance,
refuted outside, inconclusive on unit mismatch); the honest-process gate rejects fabricated
measurements but PASSES on an honest refutation.
"""

from __future__ import annotations

import math

import pytest

from gen.core.errors import UngroundedExperimentError, UnsourcedMeasurementError
from gen.core.state import (
    Claim,
    ClaimStatus,
    EmpiricalStatus,
    FalsificationExperiment,
    Measurement,
    SourceRef,
)
from gen.reality import evaluate_reality, gate_delta_plus


def _exp(tol: float = 0.01) -> FalsificationExperiment:
    return FalsificationExperiment(
        id="exp1", measurand="standard gravity", predicted_value=9.80665,
        predicted_unit="m/s^2", tolerance=tol, method="drop test in vacuum",
        grounding=["c_g"],
    )


def _meas(value: float, unit: str = "m/s^2", retrieved: bool = True, exp_id: str = "exp1") -> Measurement:
    return Measurement(id="m1", experiment_id=exp_id, value=value, unit=unit,
                       sources=[SourceRef(url_or_id="lab://run-1", retrieved=retrieved)])


def _claims() -> list[Claim]:
    return [Claim(id="c_g", text="standard gravity is 9.80665 m/s^2",
                  sources=[SourceRef(url_or_id="s", retrieved=True)],
                  status=ClaimStatus.VERIFIED, confidence=0.9)]


# --- data-model teeth ---------------------------------------------------------
def test_measurement_without_provenance_is_impossible():
    with pytest.raises(UnsourcedMeasurementError):
        Measurement(id="m0", experiment_id="exp1", value=9.8, unit="m/s^2", sources=[])


def test_experiment_without_grounding_is_impossible():
    with pytest.raises(UngroundedExperimentError):
        FalsificationExperiment(id="e0", measurand="x", predicted_value=1.0,
                                predicted_unit="m", tolerance=0.0, method="m", grounding=[])


def test_experiment_rejects_bad_tolerance_and_unit():
    with pytest.raises(ValueError):
        FalsificationExperiment(id="e1", measurand="x", predicted_value=1.0,
                                predicted_unit="m", tolerance=-1.0, method="m", grounding=["c"])
    with pytest.raises(ValueError):
        FalsificationExperiment(id="e2", measurand="x", predicted_value=1.0,
                                predicted_unit="  ", tolerance=0.0, method="m", grounding=["c"])


# --- evaluate_reality ---------------------------------------------------------
def test_within_tolerance_corroborates():
    v = evaluate_reality(_exp(), _meas(9.81))
    assert v.status is EmpiricalStatus.CORROBORATED and v.within_tolerance


def test_outside_tolerance_refutes():
    v = evaluate_reality(_exp(), _meas(9.5))
    assert v.status is EmpiricalStatus.REFUTED and not v.within_tolerance


def test_unit_conversion_is_dimension_safe():
    # 980.665 cm/s^2 == 9.80665 m/s^2 -> corroborated after scaling
    v = evaluate_reality(_exp(), _meas(980.665, unit="cm/s^2"))
    assert v.status is EmpiricalStatus.CORROBORATED
    assert math.isclose(v.residual, 0.0, abs_tol=1e-9)


def test_unit_dimension_mismatch_is_inconclusive():
    v = evaluate_reality(_exp(), _meas(9.8, unit="kg"))
    assert v.status is EmpiricalStatus.INCONCLUSIVE and math.isnan(v.residual)


# --- GATE δ⁺ (honest process) -------------------------------------------------
def test_gate_passes_on_legit_inputs():
    assert gate_delta_plus(_exp(), _meas(9.81), _claims()).passed


def test_gate_passes_even_on_honest_refutation():
    # an honest "refuted" is a valid outcome, NOT a gate failure
    res = gate_delta_plus(_exp(), _meas(9.5), _claims())
    assert res.passed


def test_gate_rejects_unknown_grounding():
    res = gate_delta_plus(_exp(), _meas(9.81), [])  # no claims -> grounding unknown
    assert not res.passed and any(f.code == "GROUNDING_UNKNOWN_CLAIM" for f in res.failures)


def test_gate_rejects_unretrieved_measurement():
    res = gate_delta_plus(_exp(), _meas(9.81, retrieved=False), _claims())
    assert not res.passed and any(f.code == "DEAD_MEASUREMENT_SOURCE" for f in res.failures)


def test_gate_rejects_experiment_mismatch():
    res = gate_delta_plus(_exp(), _meas(9.81, exp_id="other"), _claims())
    assert not res.passed and any(f.code == "EXPERIMENT_MISMATCH" for f in res.failures)
