"""Characterization test for discovery/surrogate.py general surrogate (build + predict).

Proves the headline claim: the module can train a genuine surrogate approximator on
samples of a KNOWN function and deliver predictions on held-out data that are:
- within a stated error bound of truth
- meaningfully better than the trivial constant-mean baseline
- equipped with an uncertainty signal that is monotone with distance (high on extrapolation)

Also exercises documented error cases (L4 negative tests) and invariants via Hypothesis.
This test lives in the same task as the module under review and imports only it (+stdlib/numpy/hypothesis which are declared).

Does NOT touch legacy test_discovery_surrogate.py or prefilter paths (protected).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given, strategies as st, settings

from gen.discovery.surrogate import (
    Surrogate,
    build_surrogate,
    predict_surrogate,
)


def _known_function(X: np.ndarray) -> np.ndarray:
    """A known non-trivial target: 1D 'physics-like' f(x) = sin(3x) * x + 0.2 * x**2 .
    Smooth, non-constant, has curvature — a good test for approximation quality.
    """
    x = X.ravel()
    return np.sin(3.0 * x) * x + 0.2 * x * x


def test_build_and_predict_on_held_out_beats_baseline_and_is_bounded():
    """Train on samples of a known function; held-out predictions must be accurate
    (RMSE bound) and strictly better than constant-mean predictor by a margin.
    This is the core 'not a hollow facade' assertion.
    """
    # Generate dense training grid (cheap here, stands for expensive physics sim)
    rng = np.random.default_rng(42)
    x_train = np.linspace(-2.0, 2.0, 25)
    X_train = x_train[:, None]
    y_train = _known_function(X_train)

    # Build surrogate (RBF)
    model = build_surrogate(X_train, y_train, length_scale=0.8, reg=1e-8)
    assert isinstance(model, Surrogate)
    assert model.X.shape == (25, 1)
    assert model.weights.shape[0] == 25

    # Held-out points (interpolation regime, distinct from train)
    x_test = np.linspace(-1.8, 1.8, 9)
    X_test = x_test[:, None]
    y_true = _known_function(X_test)

    y_pred, unc = predict_surrogate(model, X_test)
    assert y_pred.shape == (9,)
    assert unc.shape == (9,)
    assert np.all(unc >= 0.0)

    # Error bound on held-out (tight because function is smooth + dense samples)
    rmse = math.sqrt(np.mean((y_pred - y_true) ** 2))
    assert rmse < 0.35, f"surrogate RMSE {rmse} too large on held-out"

    # Better than trivial baseline (mean predictor) by meaningful margin
    y_mean = np.full_like(y_true, np.mean(y_train))
    rmse_baseline = math.sqrt(np.mean((y_mean - y_true) ** 2))
    improvement = rmse_baseline - rmse
    assert improvement > 0.2, (
        f"surrogate only {improvement:.3f} better than baseline (baseline rmse={rmse_baseline:.3f})"
    )
    # Prove it consumed the varying data (baseline not near zero on this curved target)
    assert rmse_baseline > 0.4


def test_uncertainty_is_monotone_with_distance_and_high_on_extrapolation():
    """Uncertainty must increase as we move away from training support.
    Far extrapolation must NOT be over-confidently wrong (high unc instead).
    """
    x_train = np.linspace(0.0, 1.0, 12)
    X_train = x_train[:, None]
    y_train = _known_function(X_train)
    model = build_surrogate(X_train, y_train, length_scale=0.5)

    # near point (inside)
    y_near, u_near = predict_surrogate(model, np.array([[0.5]]))
    # far extrapolation
    y_far, u_far = predict_surrogate(model, np.array([[10.0]]))
    # farther
    y_farther, u_farther = predict_surrogate(model, np.array([[50.0]]))

    # monotonicity: farther => higher or equal unc (property of our distance heuristic)
    assert u_far[0] > u_near[0]
    assert u_farther[0] >= u_far[0]

    # absolute: extrapolation unc is "honest high"
    assert u_far[0] > 5.0  # ls=0.5, dist~9.5 => unc ~ 0.05+19 >>1
    # The actual prediction may be bad far away, but unc must flag it
    # (we do not assert the value, only that caller can know to distrust it)


def test_build_surrogate_missing_data_raises_documented_error():
    """Missing/insufficient training data must fail loud with clear ValueError."""
    with pytest.raises(ValueError) as ctx1:
        build_surrogate([[0.0]], [1.0])
    assert "at least 2 training points" in str(ctx1.value)

    with pytest.raises(ValueError) as ctx2:
        build_surrogate([], [])
    assert "at least 2 training points" in str(ctx2.value)

    # mismatch
    with pytest.raises(ValueError) as ctx3:
        build_surrogate([[0.0], [1.0]], [3.0])  # 2 vs 1
    assert "same number of samples" in str(ctx3.value)


def test_predict_dimension_mismatch_and_non_surrogate_raise():
    model = build_surrogate([[0.0], [1.0], [2.0]], [0.1, 0.4, 1.1])
    with pytest.raises(ValueError) as ctx:
        predict_surrogate(model, [[0.0, 0.0]])  # 2 features vs 1
    assert "feature dimension mismatch" in str(ctx.value)

    with pytest.raises(ValueError) as ctx2:
        predict_surrogate("not a model", [0.0])  # type: ignore[arg-type]
    assert "expects a Surrogate" in str(ctx2.value)


def test_non_finite_training_data_raises():
    with pytest.raises(ValueError) as ctx:
        build_surrogate([[0.0], [np.nan]], [1.0, 2.0])
    assert "finite" in str(ctx.value).lower()

    with pytest.raises(ValueError) as ctx2:
        build_surrogate([[0.0], [np.inf]], [1.0, 2.0])
    assert "finite" in str(ctx2.value).lower()


# --- Property-based invariants (Hypothesis) ---

@settings(max_examples=30)
@given(
    n=st.integers(min_value=3, max_value=12),
    ls=st.floats(min_value=0.2, max_value=1.2),  # local support ls => near-exact reconstruction on train
)
def test_surrogate_reconstructs_training_data( n: int, ls: float):
    """Surrogate must consume the supplied (X,y) data: reconstruction error on the training points
    must be much smaller than the target's own variation (proves not a constant predictor).
    For local length_scale the RBF is near-interpolating.
    """
    rng = np.random.default_rng(123 + n)
    x = rng.uniform(-1.5, 1.5, size=n)
    X = x[:, None]
    y = _known_function(X)
    model = build_surrogate(X, y, length_scale=ls, reg=1e-8)
    y_rec, _ = predict_surrogate(model, X)
    rmse_rec = math.sqrt(np.mean((y_rec - y) ** 2))
    y_var = np.std(y) + 1e-12
    # Must be substantially better than baseline constant predictor (L2 honesty + not facade)
    assert rmse_rec < 0.15 * y_var, f"reconstruction rmse {rmse_rec} not << data std {y_var}"


@settings(max_examples=20)
@given(
    seed=st.integers(min_value=0, max_value=999),
)
def test_build_surrogate_is_deterministic(seed: int):
    """Same data + hyperparams => identical weights and identical predictions (A5 contract)."""
    rng = np.random.default_rng(seed)
    x = np.linspace(-1, 1, 8)
    X = x[:, None]
    y = _known_function(X) + rng.normal(0, 0.01, size=8)  # tiny noise to avoid trivial
    m1 = build_surrogate(X, y, length_scale=0.7, reg=1e-8)
    m2 = build_surrogate(X, y, length_scale=0.7, reg=1e-8)
    assert np.allclose(m1.weights, m2.weights)
    y_p1, u1 = predict_surrogate(m1, [[0.3]])
    y_p2, u2 = predict_surrogate(m2, [[0.3]])
    assert np.allclose(y_p1, y_p2)
    assert np.allclose(u1, u2)


@settings(max_examples=15)
@given(
    scale=st.floats(min_value=0.5, max_value=3.0),
)
def test_surrogate_predictions_scale_reasonably_with_input_scale(scale: float):
    """If we scale the target by k (homogeneous), predictions scale by k (linear model property
    of the RBF solve). Proves the surrogate actually consumes the y values.
    """
    x = np.linspace(-1.0, 1.0, 10)
    X = x[:, None]
    y = _known_function(X)
    m = build_surrogate(X, y, length_scale=1.0)
    y_p, _ = predict_surrogate(m, [[0.2]])

    y2 = y * scale
    m2 = build_surrogate(X, y2, length_scale=1.0)
    y_p2, _ = predict_surrogate(m2, [[0.2]])
    assert np.allclose(y_p2, y_p * scale, rtol=1e-3, atol=1e-4)


# --- Negative tests for the *prefilter* entrypoints (per review: prefilter lacked documented guards) ---

from gen.discovery import DiscoveryProblem, Variable
from gen.discovery import surrogate_score, prefilter
from gen.discovery.engine import candidate_from_exponents


def _tiny_problem(n: int = 1) -> DiscoveryProblem:
    xs = tuple(float(i) for i in range(1, n+1))
    ys = tuple( float(x**2) for x in xs )
    return DiscoveryProblem(
        idea="tiny",
        target=Variable("y", "1", ys),
        inputs=(Variable("x", "1", xs),),
    )


def test_surrogate_score_and_prefilter_fail_loud_on_too_few_points():
    """n<2 must raise ValueError (no silent subsample or crash inside numpy.choice)."""
    p = _tiny_problem(n=1)
    c = candidate_from_exponents(p, {"x": 2.0})
    with pytest.raises(ValueError) as ctx:
        surrogate_score(p, c)
    assert "at least 2 data points" in str(ctx.value)

    with pytest.raises(ValueError) as ctx2:
        prefilter(p, [c])
    assert "at least 2 data points" in str(ctx2.value)


def test_prefilter_and_score_reject_bad_sample_fraction():
    p = DiscoveryProblem(
        idea="ok",
        target=Variable("y", "1", (1.,2.,3.,4.)),
        inputs=(Variable("x", "1", (1.,2.,3.,4.)),),
    )
    c = candidate_from_exponents(p, {"x": 1.0})
    for bad in (0.0, -0.1, 1.1, 2.0):
        with pytest.raises(ValueError) as ctx:
            surrogate_score(p, c, sample_fraction=bad)
        assert "sample_fraction must be in (0, 1]" in str(ctx.value)

        with pytest.raises(ValueError) as ctx2:
            prefilter(p, [c], sample_fraction=bad)
        assert "sample_fraction must be in (0, 1]" in str(ctx2.value)


# --- Additional negative cases per rubber-duck review round (NaN hyperparams, ragged, discover entrypoint, predict) ---

from gen.discovery import build_surrogate as build_surrogate_pkg  # test package re-export path too
from gen.discovery import predict_surrogate as predict_surrogate_pkg
import pytest  # already present but ensure


def test_build_surrogate_rejects_nan_inf_hyperparams_and_ragged():
    X = [[0.0], [1.0], [2.0]]
    y = [0.0, 1.0, 4.0]
    for bad_ls in (float("nan"), float("inf"), -1.0, 0.0):
        with pytest.raises(ValueError) as ctx:
            build_surrogate_pkg(X, y, length_scale=bad_ls)
        assert "length_scale must be > 0 and finite" in str(ctx.value)
    for bad_reg in (float("nan"), float("inf"), -1e-9):
        with pytest.raises(ValueError) as ctx:
            build_surrogate_pkg(X, y, reg=bad_reg)
        assert "reg must be >= 0 and finite" in str(ctx.value)

    # ragged / inhomogeneous
    with pytest.raises(ValueError) as ctx:
        build_surrogate_pkg([[0.0], [1.0, 2.0]], [0.0, 1.0])
    assert "homogeneous" in str(ctx.value).lower() or "ragged" in str(ctx.value).lower()


def test_predict_surrogate_rejects_bad_x():
    m = build_surrogate_pkg([[0.], [1.], [2.]], [0., 1., 4.])
    with pytest.raises(ValueError) as ctx:
        predict_surrogate_pkg(m, [[0., 0.]])  # dim mismatch already covered but ragged shape
    # dim check happens after, but test ragged first
    with pytest.raises(ValueError) as ctx2:
        predict_surrogate_pkg(m, [[0.], [np.nan]])
    assert "finite" in str(ctx2.value).lower()

    # also package import path works
    assert predict_surrogate_pkg(m, [0.5])[0].shape == (1,)


def test_discover_prefiltered_names_its_own_entrypoint_in_error():
    """discover_prefiltered must raise with its name (not leak 'prefilter' message)."""
    from gen.discovery import DiscoveryProblem, Variable
    from gen.discovery import discover_prefiltered
    p1 = DiscoveryProblem(idea="1pt", target=Variable("y", "1", (1.0,)), inputs=(Variable("x", "1", (1.0,)),))
    with pytest.raises(ValueError) as ctx:
        discover_prefiltered(p1)
    assert "discover_prefiltered requires" in str(ctx.value)
