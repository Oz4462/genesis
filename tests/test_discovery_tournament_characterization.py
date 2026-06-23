"""Characterization / facade-detector for tournament.evolve (build doc 3.1).

Legacy ``test_discovery_tournament.py`` already pins the headline behaviour with an
x2-is-irrelevant problem (true exponents 2, 0). This file is the stronger anti-facade
probe demanded by the depth audit: the true law is a genuinely two-sided power law
(``y = C · x1^2 · x2^-1``) whose exponents BOTH differ sharply from the dimensional
least-norm pick (0.5, 0.5). If ``evolve`` were a hollow facade — returning the single-shot
candidate, or "improving" by a rationalisation trick rather than by really searching the
null space — these tests would fail, because only a genuine data-driven search over the
free π-group can travel from (0.5, 0.5) all the way to (2, -1).

The probes:
  * the under-determined case: evolution must MEASURABLY beat single-shot AND recover the
    true exponents/coefficient, while every evolved candidate stays dimensionally valid;
  * the determined case (Kepler): empty null space → honest no-search (improved=False,
    generations=0, best is the single-shot itself);
  * determinism: identical seed → byte-identical best candidate;
  * a property-based invariant (Hypothesis): for ANY true law inside the free family that
    is far enough from least-norm, evolution recovers it — the single-shot cannot.
"""

import math

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from gen.discovery import Constant, DiscoveryProblem, Variable, evolve
from gen.discovery.engine import dimensional_system, symbolic_regress
from gen.discovery.tournament import _nullspace

MU_SUN = 1.32712440018e20

#: A fixed, independent sample of two same-dimension inputs. Independent variation (not a
#: shared monotone ramp) is what lets the DATA discriminate between dimensionally-equivalent
#: power laws — without it x1 and x2 would be collinear and no law could be singled out.
_RNG = np.random.default_rng(0)
_X1 = _RNG.uniform(1.5, 4.0, 48)
_X2 = _RNG.uniform(1.5, 4.0, 48)


def _two_sided_free_pi_problem(coeff: float = 3.0, a_exp: float = 2.0):
    """``y = coeff · x1^a_exp · x2^(1-a_exp)`` over two LENGTH inputs and a LENGTH target.

    Both inputs share the dimension L, so the dimensional system ``A=[[1,1]], b=[1]`` is
    under-determined (a 1-D null space along [1,-1]); the least-norm pick is (0.5, 0.5). The
    true exponents are (a_exp, 1-a_exp), a free choice the dimension alone CANNOT make — only
    the data (and thus the null-space search) can. Returns the problem; all magnitudes stay
    positive so the power-law engine accepts them.
    """
    b_exp = 1.0 - a_exp
    y = coeff * _X1 ** a_exp * _X2 ** b_exp
    return DiscoveryProblem(
        idea="Welche Potenzgesetz-Kombination zweier gleich-dimensionierter Groessen erklaert y?",
        target=Variable("y", "m", tuple(y)),
        inputs=(Variable("x1", "m", tuple(_X1)), Variable("x2", "m", tuple(_X2))),
        run_id="tourney-char-001",
    )


def test_nullspace_is_nonempty_so_there_is_something_to_search():
    """Pin the precondition: this problem is genuinely under-determined (1 free π-group)."""
    a_matrix, _, _ = dimensional_system(_two_sided_free_pi_problem())
    assert _nullspace(a_matrix).shape[0] == 1


def test_single_shot_is_genuinely_wrong_here():
    """The facade-detector's premise: the single-shot least-norm pick really is the (0.5,0.5)
    law and really does fit badly — so any 'improvement' must be a real search, not noise."""
    single = symbolic_regress(_two_sided_free_pi_problem())[0]
    assert abs(single.exponents["x1"] - 0.5) < 1e-6
    assert abs(single.exponents["x2"] - 0.5) < 1e-6
    assert single.r_squared < 0.5  # least-norm cannot explain x1^2 / x2


def test_tournament_measurably_beats_single_shot_and_recovers_the_true_law():
    report = evolve(_two_sided_free_pi_problem(), generations=24, population=32, seed=1)

    # 1) it claims improvement AND the numbers back the claim
    assert report.improved
    assert report.best.r_squared > report.single_shot.r_squared + 0.4
    assert report.best.r_squared > 0.999

    # 2) it recovered the TRUE two-sided law (2, -1), not the least-norm (0.5, 0.5)
    assert abs(report.best.exponents["x1"] - 2.0) < 0.05
    assert abs(report.best.exponents["x2"] - (-1.0)) < 0.05
    assert abs(report.best.coefficient - 3.0) < 0.1

    # 3) every evolved candidate stayed inside the dimensional family (null-space search)
    assert report.best.dimension_ok
    assert report.best.dimension_residual < 1e-6

    # 4) the best-fitness trajectory is non-decreasing (selection truly carries the elite)
    traj = report.best_fitness_per_generation
    assert len(traj) == report.generations
    assert all(traj[i + 1] >= traj[i] - 1e-9 for i in range(len(traj) - 1))


def test_tournament_is_honest_when_the_system_is_determined():
    """Kepler: target T[s] from a[m] and the constant mu[m^3 s^-2] — the exponents are FORCED
    (empty null space). The tournament must not pretend to search: generations=0, no
    improvement, and the returned best IS the single-shot candidate."""
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    period = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    problem = DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(period)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),))

    report = evolve(problem)
    assert report.generations == 0
    assert not report.improved
    assert report.population_size == 1
    assert report.best.expression == report.single_shot.expression
    assert report.best.exponents == report.single_shot.exponents


def test_tournament_is_deterministic_for_a_fixed_seed():
    """A5 reproducibility: identical seed → byte-identical best candidate and trajectory."""
    first = evolve(_two_sided_free_pi_problem(), seed=7)
    second = evolve(_two_sided_free_pi_problem(), seed=7)
    assert first.best.expression == second.best.expression
    assert first.best.exponents == second.best.exponents
    assert first.best.coefficient == second.best.coefficient
    assert first.best_fitness_per_generation == second.best_fitness_per_generation


def test_different_seeds_still_converge_to_the_same_true_law():
    """The search is stochastic but the truth is not: different seeds must both land on the
    real law (proving the data — not a seeded artefact — drives the result)."""
    best_a = evolve(_two_sided_free_pi_problem(), seed=1).best
    best_b = evolve(_two_sided_free_pi_problem(), seed=99).best
    assert abs(best_a.exponents["x1"] - best_b.exponents["x1"]) < 0.05
    assert best_a.r_squared > 0.999 and best_b.r_squared > 0.999


# Property-based invariant: for ANY true law inside the free family that is far enough from
# the least-norm pick, evolution must recover it (R²≈1) and improve on single-shot. Hypothesis
# explores the whole 1-parameter family instead of one hand-picked point — the strongest
# possible refutation of "it only works on the one example in the test".
@settings(max_examples=25, deadline=None)
@given(a_exp=st.floats(min_value=1.4, max_value=3.0), coeff=st.floats(min_value=0.5, max_value=8.0))
def test_evolution_recovers_any_free_family_law(a_exp: float, coeff: float):
    problem = _two_sided_free_pi_problem(coeff=coeff, a_exp=a_exp)
    report = evolve(problem, generations=24, population=32, seed=1)
    assert report.improved
    assert report.best.r_squared > 0.999
    # recovered exponents lie on the true free-family point (a_exp, 1 - a_exp)
    assert abs(report.best.exponents["x1"] - a_exp) < 0.05
    assert abs(report.best.exponents["x2"] - (1.0 - a_exp)) < 0.05
