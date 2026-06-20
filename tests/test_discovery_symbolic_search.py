"""Tests for the open-form GP symbolic-regression engine (Roadmap B0).

The contract: a real, SEEDED, deterministic search that recovers NON-power-law laws the dimensional engine
cannot — judged through the same honesty gates (fit + dummy-exclusion + out-of-sample), never on fit alone.
"""

from __future__ import annotations


import numpy as np
import pytest

from gen.discovery.engine import discover_new_formulas
from gen.discovery.symbolic_search import (
    GPConfig,
    evaluate,
    gp_discover,
    gp_fit,
    mk_unary,
    mk_var,
    vars_used,
)
from gen.discovery.benchmark import (
    additive_freefall_problem,
    transcendental_sine_problem,
    gp_noise_redteam_problem,
    open_form_benchmark,
)

# small but convergent config — keeps the suite fast while still nailing the targets
CFG = GPConfig(population=150, generations=40, max_depth=4, parsimony=2e-3)


def _additive_columns():
    t = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    v = 9.80665 * t + 40.0
    return v, {"t": t}


def _sine_columns():
    x = np.linspace(0.5, 3.0, 12)
    y = 2.0 * np.sin(x) + 1.0
    return y, {"x": x}


def test_determinism_same_seed_is_bit_identical():
    y, cols = _sine_columns()
    a = gp_fit(y, cols, seed=7, cfg=CFG)
    b = gp_fit(y, cols, seed=7, cfg=CFG)
    assert a.expression == b.expression
    assert a.r_squared == b.r_squared  # exact float equality — a fixed seed must reproduce


def test_recovers_additive_law_the_power_law_engine_cannot():
    v, cols = _additive_columns()
    model = gp_fit(v, cols, seed=0, cfg=CFG)
    assert model.r_squared > 0.999
    assert "t" in model.expression


def test_recovers_transcendental_sine():
    y, cols = _sine_columns()
    model = gp_fit(y, cols, seed=0, cfg=CFG)
    assert model.r_squared > 0.999
    assert "sin" in model.expression  # a genuine operator beyond the power-law family


def test_power_law_engine_does_not_validate_open_form_targets():
    # the honest gap: the dimensional engine returns no validated law for either non-power-law target
    assert discover_new_formulas(additive_freefall_problem()).validated == ()
    assert discover_new_formulas(transcendental_sine_problem()).validated == ()


def test_gp_discover_confirms_real_non_power_law_laws():
    for problem in (additive_freefall_problem(), transcendental_sine_problem()):
        verdict = gp_discover(problem, seed=0, cfg=CFG)
        assert verdict.verdict == "bestaetigt"
        assert verdict.fit_ok and verdict.generalises and verdict.dummy_excluded


def test_hygiene_gate_rejects_noise_redteam():
    verdict = gp_discover(gp_noise_redteam_problem(), seed=0, cfg=CFG)
    # a fit on noise must NOT be confirmed; the out-of-sample check is what catches it
    assert verdict.verdict != "bestaetigt"
    assert not verdict.generalises


def test_dummy_variable_is_excluded_on_a_real_law():
    verdict = gp_discover(additive_freefall_problem(), seed=0, cfg=CFG)
    assert verdict.dummy_excluded is True


def test_parsimony_keeps_a_linear_target_simple():
    x = np.linspace(1.0, 8.0, 10)
    y = 3.0 * x + 2.0
    model = gp_fit(y, {"x": x}, seed=0, cfg=CFG)
    assert model.r_squared > 0.999
    assert model.complexity <= 5  # the affine refit means the structure can stay tiny


def test_open_form_benchmark_all_cases_pass():
    report = open_form_benchmark(seed=0, cfg=CFG)
    assert report.n_pass == report.n_total == 3
    by_name = {r.name: r for r in report.results}
    # real cases: GP confirmed AND the power-law engine did not
    assert by_name["additive freefall"].gp_verdict == "bestaetigt"
    assert by_name["additive freefall"].powerlaw_validated is False
    assert by_name["transcendental sine"].gp_verdict == "bestaetigt"
    # red-team: GP did not confirm
    assert by_name["red-team noise"].gp_verdict != "bestaetigt"


def test_evaluate_protected_domain_returns_non_finite_not_crash():
    # log of a non-positive value is a domain violation -> non-finite, handled (never an exception)
    out = evaluate(mk_unary("log", mk_var("x")), {"x": np.array([-1.0, 2.0])}, 2)
    assert not np.all(np.isfinite(out))


def test_vars_used_tracks_dependencies():
    tree = mk_unary("sin", mk_var("x"))
    assert vars_used(tree) == frozenset({"x"})


def test_empty_or_columnless_input_raises():
    with pytest.raises(ValueError):
        gp_fit(np.array([]), {"x": np.array([])}, seed=0, cfg=CFG)
    with pytest.raises(ValueError):
        gp_fit(np.array([1.0, 2.0]), {}, seed=0, cfg=CFG)
