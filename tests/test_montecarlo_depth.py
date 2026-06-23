"""Depth audit: prove montecarlo.py runs a real, seeded JCGM-101 simulation.

These tests are facade-detectors. They do NOT smoke-test that the function
returns a dict; they pin the output against the first-order GUM closed form and
against analytically known non-linear / correlated behaviour. If the body were
replaced by a canned constant, every cross-check below would fail.

Cross-checks (all against analytic ground truth):
  * LINEAR  ``a + b``  -> MC std == sqrt(u_a^2 + u_b^2)  (matches first-order GUM)
            and the symmetric 95 % half-width == ~1.96 * std.
  * NON-LINEAR ``x*x`` at mean 0, u>0 -> MC mean shifted by ~u^2 above x^2=0
            (the mean shift the linear GUM misses) -> input genuinely pushed
            through the model.
  * DETERMINISM: same inputs+seed -> byte-identical {mean,std,lo,hi};
            different seed -> different interval.
  * CORRELATION: ``a + b`` with rho=+1 -> std ~ u_a + u_b (linear add, not
            quadrature); ``a - b`` with rho=+1 -> std ~ |u_a - u_b|.
  * NEGATIVE (honest input-domain guards): coverage not in (0,1), n_samples<2,
            negative uncertainty all raise ValueError instead of silently
            returning a nan / zero-width / constant-mistreated result.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.montecarlo import montecarlo_correlated, montecarlo_uncertainty  # noqa: E402

# A sample count large enough to keep MC error (~1/sqrt(N)) small relative to the
# tolerances asserted below, yet fast. Std estimates carry ~1/sqrt(2N) relative
# error, so N=200k gives ~0.16 % — well inside the 2 % windows used here.
N = 200_000


def test_linear_model_matches_first_order_gum():
    """``a + b`` MC std must equal the GUM quadrature sqrt(u_a^2 + u_b^2)."""
    u_a, u_b = 2.0, 3.0
    res = montecarlo_uncertainty(
        "a + b", {"a": 10.0, "b": 20.0}, {"a": u_a, "b": u_b}, n_samples=N
    )
    expected_std = math.hypot(u_a, u_b)  # sqrt(4+9) = sqrt(13)
    assert res["mean"] == pytest.approx(30.0, abs=0.05)
    assert res["std"] == pytest.approx(expected_std, rel=0.02)


def test_linear_interval_is_symmetric_1_96_sigma():
    """The 95 % interval of a Gaussian sum is ~ mean +/- 1.96*std and symmetric."""
    res = montecarlo_uncertainty(
        "a + b", {"a": 0.0, "b": 0.0}, {"a": 1.0, "b": 1.0}, n_samples=N
    )
    std = res["std"]
    half_lo = res["mean"] - res["lo"]
    half_hi = res["hi"] - res["mean"]
    assert half_lo == pytest.approx(1.96 * std, rel=0.03)
    assert half_hi == pytest.approx(1.96 * std, rel=0.03)
    # symmetric about the mean
    assert half_lo == pytest.approx(half_hi, rel=0.03)


def test_nonlinear_mean_shift_x_squared():
    """For ``x*x`` at mean 0 with std u, E[x^2] = u^2 > 0 — the mean shift the
    linear GUM (which predicts 0) misses. Proves the sample is really squared."""
    u = 0.5
    res = montecarlo_uncertainty("x * x", {"x": 0.0}, {"x": u}, n_samples=N)
    # E[x^2] = Var(x) = u^2 = 0.25; linear GUM would give 0.
    assert res["mean"] == pytest.approx(u * u, rel=0.03)
    assert res["mean"] > 0.1  # unambiguously non-zero -> not a facade
    # std of x^2 for x~N(0,u) is u^2 * sqrt(2); proves the whole distribution moved.
    assert res["std"] == pytest.approx(u * u * math.sqrt(2.0), rel=0.05)


def test_nonlinear_shift_scales_with_input_uncertainty():
    """Doubling u must quadruple the mean shift of x^2 (E[x^2]=u^2) — the input
    is genuinely consumed, not ignored."""
    small = montecarlo_uncertainty("x * x", {"x": 0.0}, {"x": 0.5}, n_samples=N)
    big = montecarlo_uncertainty("x * x", {"x": 0.0}, {"x": 1.0}, n_samples=N)
    assert big["mean"] / small["mean"] == pytest.approx(4.0, rel=0.05)


def test_determinism_same_seed_byte_identical():
    """Identical inputs + seed -> byte-identical result (CLAUDE.md §5)."""
    args = ("a + b", {"a": 1.0, "b": 2.0}, {"a": 0.3, "b": 0.4})
    r1 = montecarlo_uncertainty(*args, n_samples=50_000, seed=777)
    r2 = montecarlo_uncertainty(*args, n_samples=50_000, seed=777)
    assert r1 == r2
    for key in ("mean", "std", "lo", "hi"):
        assert r1[key] == r2[key]  # exact equality, not approx


def test_different_seed_changes_interval():
    """A different seed must perturb the (finite-sample) interval."""
    args = ("a + b", {"a": 1.0, "b": 2.0}, {"a": 0.3, "b": 0.4})
    r1 = montecarlo_uncertainty(*args, n_samples=50_000, seed=1)
    r2 = montecarlo_uncertainty(*args, n_samples=50_000, seed=2)
    assert r1 != r2
    # but both estimate the same truth -> close, not wildly different
    assert r1["std"] == pytest.approx(r2["std"], rel=0.02)


def test_correlation_plus_one_addition_adds_linearly():
    """``a + b`` with rho=+1: variances add LINEARLY -> std ~ u_a + u_b, strictly
    larger than the independent quadrature sqrt(u_a^2+u_b^2)."""
    u_a, u_b = 2.0, 3.0
    res = montecarlo_correlated(
        "a + b",
        {"a": 0.0, "b": 0.0},
        {"a": u_a, "b": u_b},
        {("a", "b"): 1.0},
        n_samples=N,
    )
    assert res["std"] == pytest.approx(u_a + u_b, rel=0.02)  # 5.0, not sqrt(13)=3.61
    assert res["std"] > math.hypot(u_a, u_b)


def test_correlation_plus_one_subtraction_cancels():
    """``a - b`` with rho=+1: errors partially cancel -> std ~ |u_a - u_b|."""
    u_a, u_b = 3.0, 2.0
    res = montecarlo_correlated(
        "a - b",
        {"a": 0.0, "b": 0.0},
        {"a": u_a, "b": u_b},
        {("a", "b"): 1.0},
        n_samples=N,
    )
    assert res["std"] == pytest.approx(abs(u_a - u_b), rel=0.03)  # ~1.0


def test_correlation_independent_recovers_quadrature():
    """No correlation map -> independent inputs -> quadrature (sanity baseline)."""
    res = montecarlo_correlated(
        "a + b", {"a": 0.0, "b": 0.0}, {"a": 2.0, "b": 3.0}, n_samples=N
    )
    assert res["std"] == pytest.approx(math.hypot(2.0, 3.0), rel=0.02)


# --- NEGATIVE tests: honest input-domain guards (no silent bad values) --------

@pytest.mark.parametrize("coverage", [0.0, 1.0, -0.1, 1.5])
def test_guard_coverage_out_of_range(coverage):
    with pytest.raises(ValueError, match="coverage"):
        montecarlo_uncertainty(
            "a + b", {"a": 0.0, "b": 0.0}, {"a": 1.0, "b": 1.0},
            n_samples=N, coverage=coverage,
        )


@pytest.mark.parametrize("n_samples", [0, 1, -5])
def test_guard_n_samples_too_small(n_samples):
    # n_samples<2 would make the ddof=1 sample std divide by zero -> silent NaN.
    with pytest.raises(ValueError, match="n_samples"):
        montecarlo_uncertainty("a + b", {"a": 0.0}, {"a": 1.0}, n_samples=n_samples)


def test_guard_negative_uncertainty():
    # A negative u previously fell into the `u > 0 -> else constant` branch and
    # was SILENTLY treated as a constant. It must now fail loud.
    with pytest.raises(ValueError, match="uncertainty"):
        montecarlo_uncertainty("a + b", {"a": 0.0, "b": 0.0}, {"a": -1.0, "b": 1.0})


def test_guard_negative_uncertainty_correlated():
    with pytest.raises(ValueError, match="uncertainty"):
        montecarlo_correlated("a + b", {"a": 0.0, "b": 0.0}, {"a": 1.0, "b": -2.0})


def test_guards_apply_to_correlated_too():
    with pytest.raises(ValueError, match="coverage"):
        montecarlo_correlated(
            "a + b", {"a": 0.0, "b": 0.0}, {"a": 1.0, "b": 1.0}, coverage=0.0
        )
    with pytest.raises(ValueError, match="n_samples"):
        montecarlo_correlated("a + b", {"a": 0.0, "b": 0.0}, {"a": 1.0, "b": 1.0}, n_samples=1)


# --- PROPERTY-BASED: the linear-model GUM identity is an invariant -------------

@settings(max_examples=25, deadline=None)
@given(
    u_a=st.floats(min_value=0.1, max_value=10.0),
    u_b=st.floats(min_value=0.1, max_value=10.0),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_property_linear_std_is_quadrature(u_a, u_b, seed):
    """For ANY independent (u_a, u_b, seed), ``a + b`` MC std equals the GUM
    quadrature within Monte-Carlo error. This is the headline invariant: the MC
    sampler must AGREE with first-order GUM wherever the model is linear."""
    res = montecarlo_uncertainty(
        "a + b", {"a": 0.0, "b": 0.0}, {"a": u_a, "b": u_b},
        n_samples=80_000, seed=seed,
    )
    expected = math.hypot(u_a, u_b)
    # 80k samples -> std relative MC error ~ 1/sqrt(2N) ~ 0.25 %; 3 % is safe.
    assert res["std"] == pytest.approx(expected, rel=0.03)


@settings(max_examples=25, deadline=None)
@given(
    u_a=st.floats(min_value=0.1, max_value=10.0),
    u_b=st.floats(min_value=0.1, max_value=10.0),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_property_fully_correlated_addition_exceeds_quadrature(u_a, u_b, seed):
    """rho=+1 addition std (u_a+u_b) is always >= the independent quadrature."""
    res = montecarlo_correlated(
        "a + b", {"a": 0.0, "b": 0.0}, {"a": u_a, "b": u_b}, {("a", "b"): 1.0},
        n_samples=80_000, seed=seed,
    )
    assert res["std"] == pytest.approx(u_a + u_b, rel=0.03)
    # std must never be a finite-sample fluke below the independent floor:
    assert res["std"] > math.hypot(u_a, u_b) * 0.97
