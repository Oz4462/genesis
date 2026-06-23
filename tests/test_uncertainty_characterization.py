"""Characterization / facade-detector for ``gen.discovery.uncertainty.bootstrap_law``.

The headline claim under audit (FORSCHUNG_AUTONOMES_ERFINDEN §A2/P2): the bootstrap reports an
HONEST distribution over a discovered law, not a scheinsichere single number. Concretely:

  * On EXACT data every resample gives the identical perfect fit, so the parameter bands are
    DEGENERATE (≈zero width) and ``contains(true_value)`` holds — "no uncertainty, this law fits".
  * As NOISE enters the same problem the (informative) coefficient band WIDENS meaningfully and
    ``r2_mean`` drops below 1.0 — the band quantifies how much the data actually pins the parameter.
  * The whole thing is deterministic for a fixed seed.
  * Fewer than 3 data points is refused loudly (bootstrap needs real samples) — keine stillen Defaults.

A hollow facade (constant bands, ignored noise, swallowed too-few-points) FAILS these tests.

NOTE: this file is intentionally named ``test_uncertainty_characterization.py``; the pre-existing
``test_uncertainty.py`` targets the unrelated top-level ``gen.uncertainty`` (GUM propagation) module.

Run:  pytest tests/test_uncertainty_characterization.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.discovery.engine import DiscoveryProblem, Variable  # noqa: E402
from gen.discovery.uncertainty import bootstrap_law  # noqa: E402

# A clean square law ``y = C · x^2`` ([m^2] = [m]^2): the dimensional solve fixes the exponent at
# exactly 2 from the units, leaving the coefficient ``C`` as the single data-fit parameter — the
# canonical case where the exponent band is structurally degenerate and the coefficient band is the
# informative one. Distinct positive x-values keep every resample's design non-degenerate.
TRUE_COEFFICIENT = 3.0
X_VALUES = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)


def _square_law_problem(coefficient: float, xs: tuple[float, ...],
                        noise_scale: float = 0.0, noise_seed: int = 42) -> DiscoveryProblem:
    """Build ``y = coefficient · x^2`` over ``xs``. ``noise_scale`` > 0 applies deterministic
    multiplicative Gaussian noise (so the data stays positive) for the noisy-band case."""
    x = np.asarray(xs, dtype=float)
    y = coefficient * x**2
    if noise_scale > 0.0:
        rng = np.random.default_rng(noise_seed)
        y = y * (1.0 + rng.normal(0.0, noise_scale, size=x.shape))
    return DiscoveryProblem(
        idea="y = C * x^2",
        target=Variable("y", "m^2", tuple(float(v) for v in y)),
        inputs=(Variable("x", "m", tuple(float(v) for v in x)),),
    )


def test_exact_data_gives_degenerate_bands_that_contain_the_truth() -> None:
    """On exact data: coefficient AND exponent bands have ≈zero width, each contains its true
    value, and r2_mean is exactly 1.0 (every resample is a perfect fit)."""
    problem = _square_law_problem(TRUE_COEFFICIENT, X_VALUES)
    result = bootstrap_law(problem, n_resamples=200, seed=1)

    coeff = result.bands["coefficient"]
    exponent = result.bands["x"]
    # Degenerate (≈zero width) — the honest "no uncertainty here".
    assert coeff.width == pytest.approx(0.0, abs=1e-9)
    assert exponent.width == pytest.approx(0.0, abs=1e-9)
    # And the band actually brackets the truth.
    assert coeff.contains(TRUE_COEFFICIENT)
    assert exponent.contains(2.0)
    assert coeff.mean == pytest.approx(TRUE_COEFFICIENT, rel=1e-9)
    assert exponent.mean == pytest.approx(2.0, abs=1e-9)
    assert result.r2_mean == pytest.approx(1.0, abs=1e-12)


def test_noise_widens_the_coefficient_band_and_drops_r2() -> None:
    """The facade-killer: the same problem with noise must produce a MEANINGFULLY wider coefficient
    band than the exact case and an r2_mean below 1.0 — proving the bootstrap consumes the data
    scatter rather than echoing a canned interval."""
    exact = bootstrap_law(_square_law_problem(TRUE_COEFFICIENT, X_VALUES), n_resamples=200, seed=1)
    noisy = bootstrap_law(
        _square_law_problem(TRUE_COEFFICIENT, X_VALUES, noise_scale=0.1), n_resamples=200, seed=1)

    exact_width = exact.bands["coefficient"].width
    noisy_width = noisy.bands["coefficient"].width
    # Exact width is ≈0; noisy width must be clearly non-trivial and far wider.
    assert exact_width == pytest.approx(0.0, abs=1e-9)
    assert noisy_width > 1e-2
    assert noisy_width > exact_width + 1e-3
    # Honest fit quality: noise means no resample is perfect.
    assert noisy.r2_mean < 1.0


def test_deterministic_for_fixed_seed() -> None:
    """Two runs with the same seed must produce byte-identical bands and r2_mean (A5 reproducibility)."""
    problem = _square_law_problem(TRUE_COEFFICIENT, X_VALUES, noise_scale=0.1)
    first = bootstrap_law(problem, n_resamples=200, seed=7)
    second = bootstrap_law(problem, n_resamples=200, seed=7)

    assert first.r2_mean == second.r2_mean
    assert first.bands.keys() == second.bands.keys()
    for name, band in first.bands.items():
        other = second.bands[name]
        assert (band.mean, band.lo, band.hi, band.std) == (other.mean, other.lo, other.hi, other.std)


def test_fewer_than_three_points_raises() -> None:
    """Negative case: a 2-point problem cannot be bootstrapped — fail loud, never a fabricated band."""
    problem = _square_law_problem(TRUE_COEFFICIENT, (1.0, 2.0))
    with pytest.raises(ValueError, match="at least 3 data points"):
        bootstrap_law(problem, n_resamples=50, seed=0)


@settings(max_examples=30, deadline=None)
@given(
    coefficient=st.floats(min_value=0.1, max_value=100.0),
    n_points=st.integers(min_value=3, max_value=9),
)
def test_property_exact_data_always_degenerate_and_brackets_truth(coefficient: float, n_points: int) -> None:
    """Invariant (the headline as a property, not one hand-picked array): for ANY positive coefficient
    and any (>=3) distinct positive samples of an exact square law, EVERY resample recovers the same
    perfect fit, so the coefficient band is degenerate (≈zero width) and brackets the true coefficient.

    Note: r2_mean is intentionally NOT asserted to be exactly 1.0 here — with very few points a
    bootstrap resample can draw all-identical indices, making that resample's target constant, where
    R² is mathematically ill-defined (no variance to explain). The coefficient itself is still
    recovered exactly, so the band invariant — the actual headline — holds regardless. See the audit
    doc for this honest small-n nuance; r2_mean==1.0 is checked in the well-sampled example above."""
    xs = tuple(float(i) for i in range(1, n_points + 1))
    result = bootstrap_law(_square_law_problem(coefficient, xs), n_resamples=80, seed=3)
    coeff = result.bands["coefficient"]
    assert coeff.width == pytest.approx(0.0, abs=1e-6 * max(1.0, coefficient))
    assert coeff.contains(coefficient)
