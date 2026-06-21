"""Bootstrap uncertainty bands over a discovered law (discovery/uncertainty.py).

Pins the integrity layer: on EXACT Kepler data the band is degenerate and contains the truth (the honest
"no uncertainty, it fits exactly"); as noise enters, the coefficient band WIDENS, quantifying how much the
data actually pins the parameter. Pure numpy, offline, deterministic.
"""

import math

import numpy as np

from gen.discovery import DiscoveryProblem, Variable
from gen.discovery.benchmark import kepler_case
from gen.discovery.uncertainty import bootstrap_law


def _noisy_kepler(level=0.05, seed=3):
    p = kepler_case().problem
    rng = np.random.default_rng(seed)
    y = np.asarray(p.target.values, dtype=float)
    noisy = np.abs(y * (1.0 + level * rng.standard_normal(y.shape)))
    return DiscoveryProblem(idea=p.idea, target=Variable(p.target.name, p.target.unit, tuple(noisy)),
                            inputs=p.inputs, constants=p.constants, run_id="noisy")


def test_clean_data_band_contains_truth_and_is_degenerate():
    res = bootstrap_law(kepler_case().problem, n_resamples=200)
    assert res.bands["a"].contains(1.5)                       # the exponent truth is inside the band
    assert res.bands["coefficient"].contains(2.0 * math.pi)  # ~2pi is inside
    assert res.bands["coefficient"].width < 1e-6             # exact data -> degenerate band (no uncertainty)
    assert res.r2_mean > 0.999


def test_noise_widens_the_coefficient_band():
    clean = bootstrap_law(kepler_case().problem, n_resamples=200)
    noisy = bootstrap_law(_noisy_kepler(), n_resamples=200)
    assert noisy.bands["coefficient"].width > clean.bands["coefficient"].width  # noise -> real uncertainty
    assert noisy.bands["coefficient"].std > 0.0
    assert abs(noisy.bands["coefficient"].mean - 2.0 * math.pi) < 0.2 * (2.0 * math.pi)  # still near truth


def test_bootstrap_is_deterministic():
    a = bootstrap_law(kepler_case().problem, n_resamples=100)
    b = bootstrap_law(kepler_case().problem, n_resamples=100)
    assert a.bands["coefficient"].mean == b.bands["coefficient"].mean
    assert a.bands["a"].lo == b.bands["a"].lo


def test_too_few_points_raises():
    import pytest
    p = kepler_case().problem
    tiny = DiscoveryProblem(idea=p.idea, target=Variable(p.target.name, p.target.unit, (1.0, 2.0)),
                            inputs=(Variable("a", "m", (1.0, 2.0)),), constants=p.constants, run_id="tiny")
    with pytest.raises(ValueError):
        bootstrap_law(tiny)
