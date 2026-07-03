"""Tests for the best-first tree search with the gate as node-scoring oracle (discovery/tree_search.py).

Pins the search mechanics on a synthetic gate-scored space (finds the optimum, respects max_nodes,
dedups so a cyclic expand terminates, deterministic) and the discovery integration: from a WRONG
exponent start, the search walks to a gate-confirmed law scored ONLY by judge_candidate. Offline.
"""

import pytest

from gen.discovery.tree_search import best_first_search, directed_search


def _score(x):
    # quality peaks at x == 3; "passed" exactly at the peak.
    return (-((x - 3) ** 2), x == 3)


def _expand_unbounded(x):
    return [x - 1, x + 1]


def _expand_bounded(x):
    return [v for v in (x - 1, x + 1) if 0 <= v <= 6]   # clip to [0,6]


def test_finds_the_gate_passing_optimum():
    res = best_first_search([0], _score, _expand_unbounded, max_nodes=50)
    assert res.best is not None and res.best.state == 3 and res.best.passed
    assert res.passing and res.passing[0].state == 3


def test_dedup_makes_a_cyclic_expand_terminate():
    # without dedup, [x-1, x+1] would loop forever; a 7-state bounded space expands at most 7 nodes.
    res = best_first_search([3], _score, _expand_bounded, max_nodes=100)
    assert res.nodes_expanded <= 7


def test_respects_max_nodes_bound():
    res = best_first_search([0], _score, _expand_unbounded, max_nodes=5)
    assert res.nodes_expanded == 5


def test_is_deterministic():
    a = best_first_search([0], _score, _expand_unbounded, max_nodes=20)
    b = best_first_search([0], _score, _expand_unbounded, max_nodes=20)
    assert a.best.state == b.best.state and a.nodes_expanded == b.nodes_expanded


def test_max_nodes_must_be_positive():
    with pytest.raises(ValueError):
        best_first_search([0], _score, _expand_unbounded, max_nodes=0)


def test_directed_search_reaches_a_confirmed_law_from_a_wrong_start():
    from gen.discovery.benchmark import kepler_case

    problem = kepler_case().problem
    # start at a dimensionally WRONG exponent on a (1.0 instead of 1.5); the gate must guide the search.
    res = directed_search(problem, {"a": 1.0, "mu": -0.5}, step=0.5, max_nodes=64)
    assert res.best is not None and res.best.passed                # a gate-confirmed law was found
    a_exp, mu_exp = res.best.state
    assert abs(a_exp - 1.5) < 1e-6 and abs(mu_exp + 0.5) < 1e-6      # the true Kepler exponents
