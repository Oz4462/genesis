"""Characterization / depth-audit tests for ``gen.discovery.symbolic_search``.

Headline claim under audit: the module is a *genuine* genetic-programming symbolic-regression
search — it explores a space of expression trees and returns the one that fits the data, with
real search PROGRESS over generations — NOT a lookup table or a single hardcoded guess.

These tests fail loudly if the module is a hollow facade. They pin:

  * REDISCOVERY — data from a KNOWN closed form ``y = 3·sin(x) + 2`` (a transcendental law the
    narrow power-law ``engine.py`` provably cannot represent) is recovered with the correct
    STRUCTURE and COEFFICIENTS, and R² ≈ 1 on FRESH out-of-sample points.
  * PROGRESS — with a small population (so the initial random draw cannot already contain the
    answer) the best fitness strictly IMPROVES over generations and is monotone non-decreasing,
    proving evolution is doing real work rather than returning a first guess.
  * ABSTENTION (negative) — pure noise yields an honest ``unentschieden`` (no formula), never an
    over-fit ``bestaetigt``; the out-of-sample gate is what collapses on noise.
  * FAIL-LOUD (negative) — empty / mismatched / column-less data raise the documented ValueError
    rather than silently returning a fabricated model.
  * DETERMINISM (property) — same seed + same data → byte-identical expression (the module's
    reproducibility contract, Kernprinzip 5).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery.engine import DiscoveryProblem, Variable
from gen.discovery.symbolic_search import (
    GPConfig,
    gp_discover,
    gp_fit,
    vars_used,
)


def _r2(y: np.ndarray, y_hat: np.ndarray) -> float:
    """Plain coefficient of determination, used to score out-of-sample predictions."""
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0.0 else (1.0 if np.allclose(y, y_hat) else 0.0)


# --- REDISCOVERY: a real, non-power-law closed form is recovered exactly -------------------

def test_rediscovers_transcendental_closed_form_with_oos_generalisation() -> None:
    """``y = 3·sin(x) + 2`` is recovered: correct structure (sin), correct affine coefficients,
    and R² ≈ 1 on FRESH points the search never saw. A lookup or hardcoded guess cannot do this;
    only a genuine search over the sin/cos/exp/... operator set can."""
    x_train = np.linspace(0.2, 3.0, 40)
    y_train = 3.0 * np.sin(x_train) + 2.0

    model = gp_fit(y_train, {"x": x_train}, seed=0,
                   cfg=GPConfig(population=200, generations=40, max_depth=4))

    # (a) it actually fits the training data
    assert model.r_squared > 0.999

    # (b) the recovered STRUCTURE is the transcendental sin(x) — not a power law
    assert "sin" in model.expression
    assert vars_used(model.tree) == frozenset({"x"})

    # (c) the recovered COEFFICIENTS match the planted a=3, b=2 within tolerance
    assert model.a == pytest.approx(3.0, abs=1e-3)
    assert model.b == pytest.approx(2.0, abs=1e-3)

    # (d) OUT-OF-SAMPLE: predict on fresh x the model never trained on -> still R² ≈ 1.
    #     This is the decisive anti-overfit / anti-facade check.
    x_oos = np.linspace(3.05, 6.0, 37)
    y_oos = 3.0 * np.sin(x_oos) + 2.0
    y_pred = model.predict({"x": x_oos})
    assert _r2(y_oos, y_pred) > 0.999


# --- PROGRESS: the search genuinely improves over generations ------------------------------

def test_search_progress_fitness_strictly_improves_over_generations() -> None:
    """With a SMALL population (8) the initial random generation cannot already contain the
    answer, so a single generation gives a poor fit while many generations converge — proving
    real optimisation, not a one-shot guess. Target ``y = x²`` over a symmetric range, where a
    linear individual is near-useless (R² ≈ 0) and only the evolved ``x·x`` reaches R² ≈ 1."""
    x = np.linspace(-3.0, 3.0, 41)
    y = x * x

    one_gen = gp_fit(y, {"x": x}, seed=0,
                     cfg=GPConfig(population=8, generations=1, max_depth=4, elitism=1))
    many_gen = gp_fit(y, {"x": x}, seed=0,
                      cfg=GPConfig(population=8, generations=60, max_depth=4, elitism=1))

    # one generation is clearly imperfect; evolution closes the gap to a near-exact fit
    assert one_gen.r_squared < 0.9
    assert many_gen.r_squared > 0.999
    # strict, substantial improvement — the heart of "real search progress"
    assert many_gen.r_squared - one_gen.r_squared > 0.2


def test_search_progress_is_monotone_non_decreasing() -> None:
    """Best-so-far fitness never regresses as the generation budget grows (elitism + a fixed RNG
    order make the search a deterministic, improving trajectory). A facade returning a fixed guess
    would instead give a FLAT line at the same value regardless of budget."""
    x = np.linspace(-3.0, 3.0, 41)
    y = x * x

    r2_by_generations = [
        gp_fit(y, {"x": x}, seed=0,
               cfg=GPConfig(population=8, generations=g, max_depth=4, elitism=1)).r_squared
        for g in (1, 2, 4, 8, 16, 32, 60)
    ]

    # non-decreasing trajectory ...
    for earlier, later in zip(r2_by_generations, r2_by_generations[1:]):
        assert later >= earlier - 1e-9
    # ... that genuinely moves (not a flat hardcoded line)
    assert r2_by_generations[-1] - r2_by_generations[0] > 0.2


# --- NEGATIVE: pure noise -> honest abstention, never a fabricated law ----------------------

def test_pure_noise_yields_honest_abstention_not_overfit_law() -> None:
    """Data with no low-complexity symbolic structure (Gaussian noise vs an irrelevant x) must
    NOT be confirmed. The out-of-sample hygiene gate collapses on noise, so the verdict is the
    honest ``unentschieden`` ("I don't know"), never ``bestaetigt`` — Kernprinzip 4."""
    rng = np.random.default_rng(123)
    x = np.linspace(0.5, 5.0, 30)
    y = rng.normal(0.0, 1.0, size=30)
    problem = DiscoveryProblem(
        idea="pure noise has no closed form",
        target=Variable("y", "1", tuple(float(v) for v in y)),
        inputs=(Variable("x", "1", tuple(float(v) for v in x)),),
    )

    verdict = gp_discover(problem, seed=0,
                          cfg=GPConfig(population=150, generations=25, max_depth=4))

    assert verdict.verdict != "bestaetigt"
    assert verdict.passed is False
    # the generalisation gate is the one that exposes the overfit
    assert verdict.generalises is False
    assert verdict.gates["out_of_sample"]["passed"] is False


# --- NEGATIVE: malformed / missing data fails loud -----------------------------------------

def test_empty_target_raises_value_error() -> None:
    """Missing data is a documented error, never a silently fabricated model (keine stillen Defaults)."""
    with pytest.raises(ValueError, match="no samples"):
        gp_fit(np.array([]), {"x": np.array([])})


def test_mismatched_column_length_raises_value_error() -> None:
    with pytest.raises(ValueError, match="samples"):
        gp_fit(np.array([1.0, 2.0, 3.0]), {"x": np.array([1.0, 2.0])})


def test_no_input_columns_raises_value_error() -> None:
    with pytest.raises(ValueError, match="at least one input column"):
        gp_fit(np.array([1.0, 2.0, 3.0]), {})


# --- DETERMINISM (property) + a linear-recovery property -----------------------------------

@settings(max_examples=25, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_deterministic_same_seed_same_data_identical_model(seed: int) -> None:
    """Reproducibility contract: identical seed + identical data → byte-identical expression and
    fitness. A non-deterministic (or randomly-guessing) search would fail this."""
    x = np.linspace(-2.0, 2.0, 25)
    y = 2.0 * x + 1.0
    cfg = GPConfig(population=30, generations=12, max_depth=3)
    first = gp_fit(y, {"x": x}, seed=seed, cfg=cfg)
    second = gp_fit(y, {"x": x}, seed=seed, cfg=cfg)
    assert first.expression == second.expression
    assert first.r_squared == second.r_squared


@settings(max_examples=20, deadline=None)
@given(
    a=st.floats(min_value=-5.0, max_value=5.0).filter(lambda v: abs(v) > 0.3),
    b=st.floats(min_value=-5.0, max_value=5.0),
)
def test_recovers_arbitrary_affine_law(a: float, b: float) -> None:
    """For any affine law ``y = a·x + b`` the search recovers it (R² ≈ 1) — the affine refit makes
    the coefficients exact once the bare ``x`` structure is found, which the search always does."""
    x = np.linspace(1.0, 6.0, 30)
    y = a * x + b
    model = gp_fit(y, {"x": x}, seed=0, cfg=GPConfig(population=120, generations=20, max_depth=3))
    assert model.r_squared > 0.999
    # prediction matches the planted law on the same support
    assert np.allclose(model.predict({"x": x}), y, atol=1e-6)
