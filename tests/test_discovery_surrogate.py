"""Physics-Foundation surrogate — a cheap PREFILTER that ranks/prunes but NEVER confirms."""

import math

import numpy as np

from gen.discovery import Variable, Constant, DiscoveryProblem
from gen.discovery import surrogate_score, prefilter, discover_prefiltered, discover_new_formulas
from gen.discovery.engine import candidate_from_exponents

MU_SUN = 1.32712440018e20


def _xt_problem():
    """y = 3·x^2, with an irrelevant t [s] present — lets us build a dimensionally-WRONG
    candidate (tiny t exponent) that still fits numerically."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    t = np.array([1.0, 2.0, 1.5, 3.0, 2.5, 4.0])
    y = 3.0 * x ** 2
    return DiscoveryProblem(idea="y(x,t)", target=Variable("y", "m^2", tuple(y)),
                            inputs=(Variable("x", "m", tuple(x)), Variable("t", "s", tuple(t))))


def _kepler():
    a = np.array([5.79e10, 1.082e11, 1.496e11, 2.279e11, 7.785e11])
    T = 2.0 * math.pi * a ** 1.5 / math.sqrt(MU_SUN)
    return DiscoveryProblem(idea="Kepler", target=Variable("T", "s", tuple(T)),
                            inputs=(Variable("a", "m", tuple(a)),),
                            constants=(Constant("mu", MU_SUN, "m^3/s^2"),))


def test_surrogate_ranks_a_good_fit_above_a_poor_one():
    p = _xt_problem()
    good = candidate_from_exponents(p, {"x": 2.0, "t": 0.0})   # y = C·x^2 (true shape)
    poor = candidate_from_exponents(p, {"x": 1.0, "t": 0.0})   # y = C·x (wrong shape)
    assert surrogate_score(p, good) > surrogate_score(p, poor)
    kept = prefilter(p, [poor, good], top_k=1)
    assert len(kept) == 1 and kept[0].candidate.exponents["x"] == 2.0   # prunes the loser


def test_surrogate_never_confirms_the_gate_decides():
    """The hard rule (Risk 2): a dimensionally-IMPOSSIBLE candidate can score HIGH on the cheap
    surrogate (good numerical fit), yet the gate must still return 'widerlegt'. The surrogate
    prefilters; it never confirms."""
    p = _xt_problem()
    wrong = candidate_from_exponents(p, {"x": 2.0, "t": 1e-6})  # ~x^2 numerically, but T^1e-6 dim
    assert surrogate_score(p, wrong) > 0.99                      # surrogate says: promising
    assert not wrong.dimension_ok                               # ...but it is dimensionally broken
    from gen.discovery import judge_candidate
    verdict = judge_candidate(p, wrong)
    assert verdict.verdict == "widerlegt"                       # the GATE rejects it


def test_surrogate_api_returns_no_verdict():
    """Structural guarantee: the surrogate surface exposes scores/candidates, never a verdict."""
    p = _kepler()
    ranked = prefilter(p, [candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})])
    r = ranked[0]
    assert isinstance(r.surrogate_score, float)
    assert not hasattr(r, "verdict") and not hasattr(r, "passed")


def test_discover_prefiltered_keeps_the_winner():
    """Prefiltering before the gate must not drop the true law: Kepler is still rediscovered."""
    full = discover_new_formulas(_kepler()).validated[0]
    pre = discover_prefiltered(_kepler()).validated[0]
    assert pre.verdict == "bestaetigt"
    assert abs(pre.candidate.exponents["a"] - 1.5) < 1e-3
    assert pre.candidate.expression == full.candidate.expression


def test_surrogate_is_deterministic():
    p = _kepler()
    c = candidate_from_exponents(p, {"a": 1.5, "mu": -0.5})
    assert surrogate_score(p, c, seed=4) == surrogate_score(p, c, seed=4)
