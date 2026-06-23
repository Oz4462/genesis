"""Tests for the OpenMDAO MDO backend (inventor/optimize.OpenMdaoOptimizer).

OpenMDAO 3.44 is installed, so these run for real. They pin:

  * a genuine continuous optimization (om.Problem + ScipyOptimizeDriver/SLSQP) converges
    to a KNOWN analytic optimum — both an unconstrained paraboloid (min at (3, -1)) and a
    constrained problem whose optimum lies on the constraint (so the run is non-trivial);
  * select() returns the SAME non-dominated front as the offline ParetoOptimizer (the
    honest contract: OpenMDAO does not — and should not — filter a discrete list);
  * NEGATIVE / no-silent-default: an absent backend raises OptimizerUnavailable (no
    silent fallback), a broken/non-finite objective raises rather than returning a bogus
    number, and degenerate design-variable declarations are rejected.

Offline except for the in-process OpenMDAO solve (no network). Deterministic.
"""

import math

import pytest

from gen.core.state import DesignObjective, InverseDesignGoal, ObjectiveDirection
from gen.inventor.optimize import (
    DesignVar,
    OpenMdaoOptimizer,
    OptimizationError,
    OptimizerUnavailable,
    ParetoOptimizer,
)

om = pytest.importorskip("openmdao", reason="OpenMDAO MDO backend needs the optional openmdao package")


# --- positive: a real OpenMDAO solve reaches the known optimum -----------------------------

def test_openmdao_is_available():
    # It is installed in this environment; the backend must report that honestly.
    assert OpenMdaoOptimizer.available() is True


def test_minimize_unconstrained_paraboloid_hits_analytic_optimum():
    # f(x,y) = (x-3)^2 + (y+1)^2  ->  unique global minimum at (3, -1), f = 0.
    opt = OpenMdaoOptimizer()
    result = opt.minimize(
        lambda v: (v["x"] - 3.0) ** 2 + (v["y"] + 1.0) ** 2,
        [DesignVar("x", -50.0, 50.0, 0.0), DesignVar("y", -50.0, 50.0, 0.0)],
    )
    assert result.success is True
    assert result.driver == "SLSQP"
    assert result.x["x"] == pytest.approx(3.0, abs=1e-5)
    assert result.x["y"] == pytest.approx(-1.0, abs=1e-5)
    assert result.objective == pytest.approx(0.0, abs=1e-8)
    assert result.n_evals > 0  # it actually evaluated the objective


def test_minimize_finds_a_bound_constrained_optimum():
    # Minimise (x-10)^2 but x is boxed to [-5, 5]: the unconstrained optimum (10) is
    # infeasible, so the real optimum is the upper bound x=5 (f=25). This proves the
    # driver respects the declared bounds rather than returning the analytic vertex.
    opt = OpenMdaoOptimizer()
    result = opt.minimize(
        lambda v: (v["x"] - 10.0) ** 2,
        [DesignVar("x", -5.0, 5.0, 0.0)],
    )
    assert result.x["x"] == pytest.approx(5.0, abs=1e-5)
    assert result.objective == pytest.approx(25.0, abs=1e-4)


# --- select(): honest Pareto equivalence with the offline default --------------------------

def _goal():
    # Two MINIMIZE objectives (cost, mass): lower is better on both.
    return InverseDesignGoal(
        id="g",
        description="minimise cost and mass",
        objectives=[
            DesignObjective(id="cost", quantity_id="cost", direction=ObjectiveDirection.MINIMIZE, unit="1"),
            DesignObjective(id="mass", quantity_id="mass", direction=ObjectiveDirection.MINIMIZE, unit="1"),
        ],
    )


def test_select_matches_pareto_optimizer_on_a_handcrafted_set():
    # C is dominated by A (A is <= on both, strictly < on one); A and B are mutually
    # non-dominated (trade-off). So the front is {A, B}.
    items = [
        ("A", {"cost": 1.0, "mass": 4.0}),
        ("B", {"cost": 4.0, "mass": 1.0}),
        ("C", {"cost": 3.0, "mass": 5.0}),
    ]
    values_of = dict(items).__getitem__
    goal = _goal()

    omd = OpenMdaoOptimizer().select(items, lambda it: values_of(it[0]), goal)
    pareto = ParetoOptimizer().select(items, lambda it: values_of(it[0]), goal)

    assert [it[0] for it in omd] == [it[0] for it in pareto] == ["A", "B"]


# --- NEGATIVE: no silent default, no bogus optimum -----------------------------------------

def test_select_raises_when_backend_unavailable(monkeypatch):
    # Simulate openmdao being absent: selecting the openmdao backend must FAIL LOUD,
    # never silently behave like the offline default (which would hide a misconfig).
    monkeypatch.setattr(OpenMdaoOptimizer, "available", staticmethod(lambda: False))
    with pytest.raises(OptimizerUnavailable):
        OpenMdaoOptimizer().select([("A", {})], lambda it: {}, _goal())


def test_minimize_raises_when_backend_unavailable(monkeypatch):
    monkeypatch.setattr(OpenMdaoOptimizer, "available", staticmethod(lambda: False))
    with pytest.raises(OptimizerUnavailable):
        OpenMdaoOptimizer().minimize(lambda v: v["x"], [DesignVar("x", 0.0, 1.0, 0.5)])


def test_minimize_rejects_a_non_finite_objective_at_start():
    # A broken objective (returns NaN) must surface as an error — not be optimized into
    # some meaningless "optimum". Caught at the start point before the driver runs.
    opt = OpenMdaoOptimizer()
    with pytest.raises(ValueError):
        opt.minimize(lambda v: float("nan"), [DesignVar("x", -1.0, 1.0, 0.0)])


def test_minimize_rejects_an_objective_that_raises():
    opt = OpenMdaoOptimizer()
    with pytest.raises(ValueError):
        opt.minimize(
            lambda v: 1.0 / 0.0,  # noqa: B023 - intentional ZeroDivisionError inside objective
            [DesignVar("x", -1.0, 1.0, 0.0)],
        )


def test_minimize_raises_on_non_convergence():
    # Starve the driver (maxiter=1) on an optimum far from the start: it cannot converge,
    # and an un-converged run is a FAILED analysis — it must raise, never silently return
    # the last unconverged iterate dressed up as the optimum.
    opt = OpenMdaoOptimizer()
    with pytest.raises(OptimizationError):
        opt.minimize(
            lambda v: (v["x"] - 1.0e6) ** 2 + (v["y"] - 1.0e6) ** 2,
            [DesignVar("x", -1e9, 1e9, 0.0), DesignVar("y", -1e9, 1e9, 0.0)],
            tol=1e-14,
            maxiter=1,
        )


def test_minimize_requires_design_vars():
    with pytest.raises(ValueError):
        OpenMdaoOptimizer().minimize(lambda v: 0.0, [])


def test_minimize_rejects_duplicate_var_names():
    with pytest.raises(ValueError):
        OpenMdaoOptimizer().minimize(
            lambda v: v["x"],
            [DesignVar("x", 0.0, 1.0, 0.5), DesignVar("x", 0.0, 1.0, 0.5)],
        )


def test_designvar_rejects_start_outside_bounds():
    # No silent clamping of the start point: an out-of-box start is a declared mistake.
    with pytest.raises(ValueError):
        DesignVar("x", 0.0, 1.0, 5.0)


def test_designvar_rejects_inverted_bounds():
    with pytest.raises(ValueError):
        DesignVar("x", 1.0, 0.0, 0.5)


def test_unconstrained_optimum_is_deterministic():
    opt = OpenMdaoOptimizer()
    dvs = [DesignVar("x", -50.0, 50.0, 0.0), DesignVar("y", -50.0, 50.0, 0.0)]
    fn = lambda v: (v["x"] - 3.0) ** 2 + (v["y"] + 1.0) ** 2  # noqa: E731
    a = opt.minimize(fn, dvs)
    b = opt.minimize(fn, dvs)
    assert math.isclose(a.x["x"], b.x["x"]) and math.isclose(a.x["y"], b.x["y"])
