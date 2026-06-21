"""Minimal-correction discovery when sourced laws are composed — "does the naive composition hold,
and if not, what is the smallest correction?". Residual-scoped dimensional SR on a SIGNED residual,
gated honestly so noise is never promoted to a coupling law.
"""

import numpy as np
import pytest

from gen.discovery import (
    Constant, DiscoveryProblem, Variable,
    CompositionResult, discover_correction,
)

_X = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
_K = 0.3


def _coupling_problem() -> tuple[DiscoveryProblem, np.ndarray]:
    """True law y = x + ½·k·x²; the naive baseline is the linear part x, so the composition MISSES
    the ½·k·x² coupling. Returns (problem, baseline_prediction)."""
    y = _X + 0.5 * _K * _X**2
    problem = DiscoveryProblem(
        idea="Superposition", target=Variable("y", "m", tuple(y)),
        inputs=(Variable("x", "m", tuple(_X)),), constants=(Constant("k", _K, "1/m"),))
    return problem, _X.copy()        # baseline = x


def _nonzero(exps: dict[str, float]) -> dict[str, float]:
    return {k: v for k, v in exps.items() if abs(v) > 1e-9}


def test_discovers_the_minimal_coupling_correction():
    """The naive linear baseline misses the ½·k·x² term; discover_correction recovers exactly that
    term (coef ½, exponents x², k¹), completes the fit (R²≈1), and reports korrektur_noetig."""
    problem, baseline = _coupling_problem()
    res = discover_correction(problem, baseline)
    assert isinstance(res, CompositionResult)
    assert res.verdict == "korrektur_noetig"
    # Measured evidence per spec: ~0.16 for this construction (y = x + 0.5 k x^2, baseline=x)
    assert res.baseline_r2 < 0.2 and res.baseline_r2 > 0.1
    assert abs(res.corrected_r2 - 1.0) < 1e-9
    assert abs(res.residual_explained - 1.0) < 1e-9
    assert res.n_terms == 1
    term = res.correction_terms[0]
    assert not term.is_intercept
    assert _nonzero(term.exponents) == {"x": 2.0, "k": 1.0}
    assert abs(term.coefficient - 0.5) < 1e-6


def test_a_complete_composition_needs_no_correction():
    """When the baseline already equals the data (residual = 0) the verdict is vollstaendig and no
    correction is asserted — never a spurious term fitted to nothing."""
    problem, _ = _coupling_problem()
    y = np.asarray(problem.target.values, float)
    res = discover_correction(problem, y)        # baseline == y
    assert res.verdict == "vollstaendig"
    assert res.n_terms == 0
    assert res.baseline_r2 > 0.999


def test_noise_residual_is_not_promoted_to_a_correction():
    """A residual that is pure noise (no dimensional structure) does NOT become a 'coupling law':
    the residual-explained gate keeps the verdict vollstaendig (anti-hallucination, δ-asymmetry)."""
    rng = np.random.default_rng(3)
    y = _X + rng.uniform(-2.0, 2.0, size=_X.shape)        # linear + unstructured noise
    problem = DiscoveryProblem(
        idea="Rauschen", target=Variable("y", "m", tuple(y)),
        inputs=(Variable("x", "m", tuple(_X)),), constants=(Constant("k", _K, "1/m"),))
    res = discover_correction(problem, _X.copy())
    assert res.verdict == "vollstaendig"
    # With this noise level the structured term explains only ~0.21 of residual variance (<0.9 gate)
    assert res.residual_explained < 0.5
    assert res.n_terms == 0


def test_correction_is_dimensionally_consistent_with_the_target():
    """The discovered correction term carries the target's dimension (it is a real additive
    correction, not a dimensionally-impossible fudge): x²·k = m²·(1/m) = m = [y]."""
    problem, baseline = _coupling_problem()
    res = discover_correction(problem, baseline)
    # x²·k has dimension m²·m⁻¹ = m, exactly the target unit "m" — verified structurally here
    assert _nonzero(res.correction_terms[0].exponents) == {"x": 2.0, "k": 1.0}
    assert "x^2" in res.correction_expression and "k" in res.correction_expression


def test_rejects_a_baseline_of_the_wrong_length():
    """The baseline prediction must align with the target; a length mismatch is a hard ValueError."""
    problem, _ = _coupling_problem()
    with pytest.raises(ValueError):
        discover_correction(problem, np.array([1.0, 2.0, 3.0]))      # too short


def test_reports_how_large_the_correction_is():
    """The result quantifies the correction's size (RMS(correction)/RMS(y)) — the basis for a
    'superposition holds to ~X %' statement."""
    problem, baseline = _coupling_problem()
    res = discover_correction(problem, baseline)
    assert 0.0 < res.relative_correction < 1.0


def test_a_real_correction_survives_leave_one_out():
    """The actual defence behind the in-sample bar: the correction is asserted only because it
    GENERALISES out-of-fold (leave-one-out R² near 1), not merely because it fit the points it was
    trained on. A term fitting structured noise would collapse here (often negative)."""
    problem, baseline = _coupling_problem()
    res = discover_correction(problem, baseline)
    assert res.verdict == "korrektur_noetig"
    assert res.loo_r2 > 0.99
