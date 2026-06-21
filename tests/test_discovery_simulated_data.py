"""Self-generated-data discovery (INVENTOR §10): the dimensional SR engine recovers a law from data GENESIS
samples ITSELF from a simulator/closed form — not from any supplied dataset. Deterministic, offline.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.discovery.engine import Constant  # noqa: E402
from gen.discovery.simulated_data import (  # noqa: E402
    InputSpec,
    discover_from_simulation,
    problem_from_simulation,
)


def test_recovers_kinetic_energy_from_self_generated_data():
    res = discover_from_simulation(
        "kinetische Energie", target_name="E", target_unit="J",
        inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
        sim_fn=lambda m, v: 0.5 * m * v ** 2, n_samples=200, seed=0)
    assert res.validated
    top = res.validated[0].candidate
    assert round(top.exponents["m"], 3) == 1.0 and round(top.exponents["v"], 3) == 2.0
    assert top.r_squared == pytest.approx(1.0, abs=1e-9) and top.dimension_ok
    assert res.validated[0].verdict == "bestaetigt"


def test_recovers_pendulum_period_with_a_constant():
    # T = 2π·sqrt(L/g): only L is sampled, g is a known constant — the dimensional solve must give L^0.5 g^-0.5
    res = discover_from_simulation(
        "Pendelperiode", target_name="T", target_unit="s",
        inputs=(InputSpec("L", "m", 0.1, 10.0),),
        sim_fn=lambda L, g: 2.0 * math.pi * (L / g) ** 0.5,
        constants=(Constant("g", 9.80665, "m/s^2"),), n_samples=200, seed=1)
    assert res.validated
    top = res.validated[0].candidate
    assert round(top.exponents["L"], 3) == 0.5
    assert top.r_squared == pytest.approx(1.0, abs=1e-9)


def test_is_deterministic_given_the_seed():
    kw = dict(target_name="E", target_unit="J",
              inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
              sim_fn=lambda m, v: 0.5 * m * v ** 2, n_samples=64, seed=7)
    a = discover_from_simulation("e", **kw).validated[0].candidate.expression
    b = discover_from_simulation("e", **kw).validated[0].candidate.expression
    assert a == b


def test_self_generated_problem_has_matching_sample_lengths():
    problem, baked = problem_from_simulation(
        "e", target_name="E", target_unit="J",
        inputs=(InputSpec("m", "kg", 0.1, 10.0), InputSpec("v", "m/s", 0.1, 10.0)),
        sim_fn=lambda m, v: 0.5 * m * v ** 2, n_samples=50, seed=0)
    assert len(problem.target.values) == 50
    assert all(len(iv.values) == 50 for iv in problem.inputs)
    assert baked(m=2.0, v=3.0) == pytest.approx(0.5 * 2.0 * 9.0)


def test_rejects_a_non_positive_target():
    with pytest.raises(ValueError):
        problem_from_simulation("bad", target_name="y", target_unit="J",
                                inputs=(InputSpec("x", "m", 0.1, 1.0),),
                                sim_fn=lambda x: -x, n_samples=10, seed=0)


def test_rejects_a_bad_input_range():
    with pytest.raises(ValueError):
        InputSpec("x", "m", 5.0, 1.0)        # lo >= hi
