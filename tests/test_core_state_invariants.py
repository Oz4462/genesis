"""Core state invariants (REWORK campaign 2026-07-11).

Pins the structural anti-hallucination rules on Claim / SourceRef / Measurement
at construction time — belt-and-suspenders with agent-level clamps and gates.
"""

from __future__ import annotations

import math

import pytest

from gen.core.errors import UnsourcedClaimError, UnsourcedMeasurementError
from gen.core.state import (
    Claim,
    ClaimStatus,
    Measurement,
    SourceRef,
    SourceSupport,
)


def _src(**kw) -> SourceRef:
    base = dict(url_or_id="https://example.test/s", retrieved=True)
    base.update(kw)
    return SourceRef(**base)


# --- Claim: no fact without provenance ---------------------------------------


def test_claim_rejects_empty_sources():
    with pytest.raises(UnsourcedClaimError):
        Claim(id="c1", text="steel is dense", sources=[])


def test_claim_rejects_blank_source_url():
    with pytest.raises(ValueError, match="url_or_id"):
        Claim(id="c1", text="steel is dense", sources=[_src(url_or_id="  ")])


def test_claim_rejects_empty_text():
    with pytest.raises(ValueError, match="text"):
        Claim(id="c1", text="   ", sources=[_src()])


def test_claim_accepts_minimal_valid():
    c = Claim(id="c1", text="steel density is about 7850 kg/m3", sources=[_src()])
    assert c.status is ClaimStatus.UNVERIFIED
    assert c.confidence == 0.0


# --- Claim: confidence must be a real probability ----------------------------


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_claim_rejects_nonfinite_confidence(bad: float):
    with pytest.raises(ValueError, match="confidence"):
        Claim(id="c1", text="x", sources=[_src()], confidence=bad)


@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -1.0])
def test_claim_rejects_confidence_outside_unit_interval(bad: float):
    with pytest.raises(ValueError, match="confidence"):
        Claim(id="c1", text="x", sources=[_src()], confidence=bad)


@pytest.mark.parametrize("ok", [0.0, 0.5, 1.0])
def test_claim_accepts_confidence_on_unit_interval(ok: float):
    c = Claim(id="c1", text="x", sources=[_src()], confidence=ok)
    assert c.confidence == ok
    assert math.isfinite(c.confidence)


# --- SourceRef ---------------------------------------------------------------


def test_source_ref_support_defaults_to_supports():
    s = SourceRef(url_or_id="https://example.test/s", retrieved=True)
    assert s.support is SourceSupport.SUPPORTS


def test_source_ref_accepts_contradicts():
    s = _src(support=SourceSupport.CONTRADICTS)
    assert s.support is SourceSupport.CONTRADICTS


# --- Measurement (δ⁺ integrity) ----------------------------------------------


def test_measurement_requires_retrieved_source():
    with pytest.raises(UnsourcedMeasurementError):
        Measurement(
            id="m1",
            experiment_id="e1",
            value=9.81,
            unit="m/s2",
            sources=[_src(retrieved=False)],
        )


def test_measurement_rejects_nonfinite_value():
    with pytest.raises(ValueError, match="finite"):
        Measurement(
            id="m1",
            experiment_id="e1",
            value=float("nan"),
            unit="m/s2",
            sources=[_src()],
        )


def test_measurement_accepts_retrieved_finite():
    m = Measurement(
        id="m1",
        experiment_id="e1",
        value=9.81,
        unit="m/s2",
        sources=[_src()],
    )
    assert m.value == pytest.approx(9.81)
