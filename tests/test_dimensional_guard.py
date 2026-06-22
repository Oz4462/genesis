"""Tests for dimensional_guard — scale-invariance detection of DIMENSIONAL formula errors.

The module's contract: a closed-form check returns a dimensionless ``safety_factor`` (a ratio
of two same-dimension quantities). If the underlying formula is dimensionally HOMOGENEOUS in its
inputs, that number must not move when the base units are coherently rescaled; if it moves, a term
is dimensionally inconsistent. These tests drive the public API with tiny toy functions so they
need no real validator — a homogeneous ratio fn (invariant) and a non-homogeneous summing fn
(not invariant) are enough to exercise every branch.

Offline, deterministic, stdlib + Hypothesis only.

Run:  pytest tests/test_dimensional_guard.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402
from hypothesis import given  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from gen.dimensional_guard import (  # noqa: E402
    DimensionalInconsistencyError,
    assert_scale_invariant,
    parse_unit,  # re-exported transitively from verification.units
    scale_invariance_report,
)


# --- toy validators driving the API -----------------------------------------
#
# A HOMOGENEOUS check: safety_factor is a ratio of two same-dimension inputs, so it is
# dimensionless and invariant under any coherent unit rescaling.
def homogeneous_ratio(allowable: float, actual: float) -> dict:
    """allowable/actual — dimensionless when both carry the same unit."""
    return {"safety_factor": allowable / actual}


# A NON-HOMOGENEOUS check: it ADDS two incommensurable inputs (a length and a mass). The sum is
# dimensionally meaningless, so it changes under rescaling — exactly the error class the module
# catches without knowing the "right" answer.
def non_homogeneous_sum(length: float, mass: float) -> dict:
    """length + mass — incommensurable; rescaling length (L) and mass (M) by different factors
    moves the result, so safety_factor is NOT invariant."""
    return {"safety_factor": length + mass}


def test_units_used_actually_parse() -> None:
    """Guard the test's own premise: every unit string below must parse (no opaque atoms),
    otherwise an unknown unit would silently default to scale 1.0 and mask a real move."""
    for unit in ("Pa", "m", "kg"):
        dims = parse_unit(unit).as_dict()
        assert dims, f"{unit!r} parsed to dimensionless/opaque-free unexpectedly: {dims}"
    # the two summed inputs must carry GENUINELY different dimensions, else the sum would be
    # accidentally homogeneous and the negative test would be vacuous.
    assert parse_unit("m").as_dict() != parse_unit("kg").as_dict()


# --- (a) homogeneous fn -> invariant True, rel_change ~ 0 --------------------
def test_homogeneous_ratio_is_invariant() -> None:
    inputs = {"allowable": (250.0, "Pa"), "actual": (100.0, "Pa")}
    rep = scale_invariance_report(homogeneous_ratio, inputs)
    assert rep["invariant"] is True
    assert rep["base"] == pytest.approx(2.5)
    assert rep["rescaled"] == pytest.approx(2.5)
    # both inputs share the Pa scale factor, so it cancels in the ratio -> exactly no change.
    assert rep["rel_change"] == pytest.approx(0.0, abs=1e-12)


# --- (b) non-homogeneous fn -> invariant False ------------------------------
def test_non_homogeneous_sum_is_not_invariant() -> None:
    inputs = {"length": (4.0, "m"), "mass": (3.0, "kg")}
    rep = scale_invariance_report(non_homogeneous_sum, inputs)
    assert rep["invariant"] is False
    # base = 4 + 3 = 7; length scales by L=2.0, mass by M=3.0 -> 8 + 9 = 17, genuinely moved.
    assert rep["base"] == pytest.approx(7.0)
    assert rep["rescaled"] == pytest.approx(17.0)
    assert rep["rel_change"] > 0.0


# --- (c) assert_scale_invariant: returns report / raises --------------------
def test_assert_returns_report_on_homogeneous() -> None:
    inputs = {"allowable": (300.0, "Pa"), "actual": (150.0, "Pa")}
    rep = assert_scale_invariant(homogeneous_ratio, inputs)
    assert rep["invariant"] is True
    assert rep["base"] == pytest.approx(2.0)


def test_assert_raises_on_non_homogeneous() -> None:
    inputs = {"length": (4.0, "m"), "mass": (3.0, "kg")}
    with pytest.raises(DimensionalInconsistencyError):
        assert_scale_invariant(non_homogeneous_sum, inputs)


def test_inconsistency_error_is_assertion_error_subclass() -> None:
    # Documented contract: the raised error IS an AssertionError so existing assert-based
    # harnesses catch it without importing the specific type.
    assert issubclass(DimensionalInconsistencyError, AssertionError)
    inputs = {"length": (1.0, "m"), "mass": (1.0, "kg")}
    with pytest.raises(AssertionError):
        assert_scale_invariant(non_homogeneous_sum, inputs)


# --- (d) zero / non-finite base branch: exact-equality comparison -----------
def test_zero_base_compares_by_exact_equality() -> None:
    # base == 0.0 takes the exact-equality branch; a fn that always returns 0.0 stays 0.0 under
    # rescaling -> invariant True with rel_change pinned to exactly 0.0 (no 0/0 division).
    rep = scale_invariance_report(lambda allowable, actual: {"safety_factor": 0.0},
                                  {"allowable": (1.0, "Pa"), "actual": (2.0, "Pa")})
    assert rep["base"] == 0.0
    assert rep["invariant"] is True
    assert rep["rel_change"] == 0.0


def test_non_finite_base_compares_by_exact_equality() -> None:
    # A non-finite base (inf) also takes the exact-equality branch; inf == inf -> invariant True,
    # rel_change exactly 0.0, never NaN from inf - inf.
    rep = scale_invariance_report(lambda allowable, actual: {"safety_factor": float("inf")},
                                  {"allowable": (1.0, "Pa"), "actual": (2.0, "Pa")})
    assert math.isinf(rep["base"])
    assert rep["invariant"] is True
    assert rep["rel_change"] == 0.0


# --- property: a same-dimension ratio is ALWAYS invariant -------------------
@given(
    allowable=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False),
    actual=st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_property_same_dimension_ratio_always_invariant(allowable: float, actual: float) -> None:
    """Invariant: for ANY positive same-unit (allowable, actual), the scale factor cancels in the
    ratio, so the dimensionless verdict cannot move under rescaling. Property-based because the
    homogeneity guarantee must hold for the whole input space, not a few picked points."""
    inputs = {"allowable": (allowable, "Pa"), "actual": (actual, "Pa")}
    rep = scale_invariance_report(homogeneous_ratio, inputs)
    assert rep["invariant"] is True
    assert rep["rel_change"] == pytest.approx(0.0, abs=1e-9)
