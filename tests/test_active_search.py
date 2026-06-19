"""Tests for the InfoBAX-style active candidate selection (discovery/active_search.py).

Pins: binary entropy peaks at p=0.5; the pass-probability model interpolates between gated examples and
is most uncertain at the boundary; selection targets the most-informative candidate; and the active
loop finds a passing candidate within a budget smaller than the pool, with the gate as the only oracle
(no false passing). Offline, deterministic.
"""

import pytest

from gen.discovery.active_search import (
    PassModel,
    active_select,
    binary_entropy,
    select_most_informative,
)


def test_binary_entropy_peaks_at_one_half():
    assert binary_entropy(0.5) == 1.0
    assert binary_entropy(0.0) == 0.0 and binary_entropy(1.0) == 0.0
    assert binary_entropy(0.5) > binary_entropy(0.25) > binary_entropy(0.02)


def test_pass_model_is_most_uncertain_at_the_boundary():
    model = PassModel([((0.0,), True), ((10.0,), False)])
    assert model.predict((0.0,)) > 0.95 and model.predict((10.0,)) < 0.05
    assert abs(model.predict((5.0,)) - 0.5) < 1e-9             # equidistant -> maximally uncertain
    assert model.predict((4.0,)) > model.predict((6.0,))      # closer to the passing example


def test_empty_model_is_neutral():
    assert PassModel([]).predict((3.0,)) == 0.5


def test_selects_the_boundary_candidate():
    model = PassModel([((0.0,), True), ((10.0,), False)])
    # the boundary point (5,) is most informative; the confident endpoints are not.
    assert select_most_informative([(0.0,), (5.0,), (10.0,)], model) == 1


def test_active_loop_finds_a_pass_within_budget_with_gate_as_oracle():
    pool = list(range(10))
    gate = lambda x: 4 <= x <= 6                                # the (unknown to the policy) passing region
    feature = lambda x: (float(x),)
    res = active_select(pool, gate, feature, budget=6)
    assert res.gate_calls == 6                                  # spent exactly the budget
    assert res.passing                                          # found at least one passing candidate
    assert all(4 <= c <= 6 for c in res.passing)               # the gate, not the policy, decided pass


def test_active_loop_is_deterministic():
    pool = list(range(10))
    gate = lambda x: 4 <= x <= 6
    feature = lambda x: (float(x),)
    a = active_select(pool, gate, feature, budget=6)
    b = active_select(pool, gate, feature, budget=6)
    assert a.gated == b.gated


def test_negative_budget_rejected():
    with pytest.raises(ValueError):
        active_select([1, 2], lambda x: True, lambda x: (float(x),), budget=-1)
