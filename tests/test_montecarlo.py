"""Monte-Carlo uncertainty (JCGM 101) vs the first-order GUM (JCGM 100).

The Monte-Carlo propagation must AGREE with the first-order GUM where the model is
linear (that is the cross-check), and must CAPTURE non-linearity where first-order
cannot — most visibly the mean shift of y = x^2, which the linear method leaves at
the point value. The sampler is seeded, so results are deterministic.

Offline, no LLM.

Run:  pytest tests/test_montecarlo.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.montecarlo import montecarlo_uncertainty  # noqa: E402
from gen.uncertainty import combine_standard_uncertainty  # noqa: E402


def test_linear_agrees_with_first_order_gum():
    values, uncs = {"m": 12.0, "g": 9.80665}, {"m": 0.5}
    mc = montecarlo_uncertainty("m * g", values, uncs)
    gum = combine_standard_uncertainty("m * g", values, uncs)
    assert math.isclose(mc["std"], gum, rel_tol=2e-2)          # within Monte-Carlo error
    assert math.isclose(mc["mean"], 12.0 * 9.80665, rel_tol=2e-3)  # linear: no mean shift


def test_sum_in_quadrature_matches():
    mc = montecarlo_uncertainty("a + b", {"a": 10.0, "b": 20.0}, {"a": 3.0, "b": 4.0})
    assert math.isclose(mc["std"], 5.0, rel_tol=2e-2)          # sqrt(3^2 + 4^2)


def test_nonlinearity_captured_as_mean_shift():
    # y = x^2, x = 10 +/- 1: the first-order method leaves the value at 100, but the
    # true mean is E[x^2] = 100 + var = 101. Monte Carlo recovers the +1 shift.
    mc = montecarlo_uncertainty("x * x", {"x": 10.0}, {"x": 1.0})
    assert mc["mean"] > 100.5                                  # the shift first-order misses
    assert math.isclose(mc["mean"], 101.0, abs_tol=0.2)


def test_is_deterministic_for_fixed_seed():
    a = montecarlo_uncertainty("x * x", {"x": 10.0}, {"x": 1.0})
    b = montecarlo_uncertainty("x * x", {"x": 10.0}, {"x": 1.0})
    assert a == b
    # a different seed gives a (slightly) different draw
    c = montecarlo_uncertainty("x * x", {"x": 10.0}, {"x": 1.0}, seed=999)
    assert c["mean"] != a["mean"]


def test_coverage_interval_brackets_the_mean():
    mc = montecarlo_uncertainty("x * x", {"x": 10.0}, {"x": 1.0})
    assert mc["lo"] < mc["mean"] < mc["hi"]


def test_exact_input_gives_zero_spread():
    mc = montecarlo_uncertainty("a + b", {"a": 5.0, "b": 7.0}, {})   # no uncertainties
    assert math.isclose(mc["std"], 0.0, abs_tol=1e-12)
    assert math.isclose(mc["mean"], 12.0, rel_tol=1e-12)
