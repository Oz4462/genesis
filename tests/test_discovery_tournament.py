"""Tournament — population evolution must MEASURABLY beat single-shot (build doc 3.1 DoD)."""

import math

import numpy as np

from gen.discovery import Variable, Constant, DiscoveryProblem
from gen.discovery import evolve

MU_SUN = 1.32712440018e20


def _free_pi_problem():
    """y = 3·x1^2, with an irrelevant SAME-dimension x2 — so the dimensional system is
    under-determined and the single-shot least-norm pick (x1·x2) is wrong; only the data
    (and thus evolution over the null space) finds x1^2."""
    x1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    x2 = np.array([1.5, 3.0, 1.0, 4.0, 2.0, 5.0, 2.5])
    y = 3.0 * x1 ** 2
    return DiscoveryProblem(
        idea="Wovon hängt y ab, wenn zwei gleich-dimensionierte Größen vorliegen?",
        target=Variable("y", "m^2", tuple(y)),
        inputs=(Variable("x1", "m", tuple(x1)), Variable("x2", "m", tuple(x2))),
        run_id="tourney-001")


def test_tournament_beats_single_shot_on_a_free_pi_group():
    report = evolve(_free_pi_problem(), generations=24, population=32, seed=1)
    assert report.improved
    assert report.best.r_squared > report.single_shot.r_squared + 0.05   # measurably better
    assert report.best.r_squared > 0.999
    # it recovered y = 3 * x1^2 (x1 exponent ~2, x2 ~0), all WITHIN the dimensional family
    assert abs(report.best.exponents["x1"] - 2.0) < 0.05
    assert abs(report.best.exponents["x2"]) < 0.05
    assert abs(report.best.coefficient - 3.0) < 0.1
    assert report.best.dimension_ok                                       # never left the family


def test_tournament_is_honest_when_nothing_to_search():
    """Kepler is dimensionally DETERMINED — the null space is empty, so there is nothing to
    evolve; the tournament returns the single-shot candidate and claims no improvement."""
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    problem = DiscoveryProblem(
        idea="Kepler", target=Variable("T", "s", tuple(T)),
        inputs=(Variable("a", "m", tuple(a)),),
        constants=(Constant("mu", MU_SUN, "m^3/s^2"),))
    report = evolve(problem)
    assert report.generations == 0 and not report.improved
    assert report.best.expression == report.single_shot.expression


def test_tournament_is_deterministic():
    a = evolve(_free_pi_problem(), seed=7).best
    b = evolve(_free_pi_problem(), seed=7).best
    assert a.expression == b.expression and a.coefficient == b.coefficient
