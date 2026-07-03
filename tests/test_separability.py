"""Tests for AI-Feynman separability detection (discovery/separability.py).

Pins the mixed-second-difference test: a pure sum/product separates into singletons under the matching
mode; a product does NOT separate additively; a mixed law (a*b + c) correctly groups the multiplied
pair and splits off the additive term; multiplicative mode requires positivity. Offline, deterministic.
"""

import pytest

from gen.discovery.separability import analyze_separability

_R = {"a": (1.0, 3.0), "b": (1.0, 3.0), "c": (1.0, 3.0)}


def test_pure_sum_is_fully_additively_separable():
    r = analyze_separability(lambda a, b, c: a + b + c, ["a", "b", "c"], _R, mode="additive")
    assert {frozenset({"a"}), frozenset({"b"}), frozenset({"c"})} == set(r.groups)
    assert r.max_interaction == 0.0


def test_pure_product_is_fully_multiplicatively_separable():
    r = analyze_separability(lambda a, b, c: a * b * c, ["a", "b", "c"], _R, mode="multiplicative")
    assert len(r.groups) == 3 and r.max_interaction == 0.0


def test_product_is_not_additively_separable():
    r = analyze_separability(lambda a, b: a * b, ["a", "b"], _R, mode="additive")
    assert r.groups == (frozenset({"a", "b"}),)          # they interact -> one group
    assert r.max_interaction > 0.0


def test_mixed_law_groups_the_product_and_splits_the_additive_term():
    # a*b + c : a and b interact (multiplied); c is additive and separates off.
    r = analyze_separability(lambda a, b, c: a * b + c, ["a", "b", "c"], _R, mode="additive")
    assert set(r.groups) == {frozenset({"a", "b"}), frozenset({"c"})}


def test_multiplicative_mode_requires_positive_target():
    with pytest.raises(ValueError):
        analyze_separability(lambda a, b: a - 5.0, ["a", "b"], _R, mode="multiplicative")


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        analyze_separability(lambda a, b: a + b, ["a", "b"], _R, mode="nonsense")


def test_is_deterministic():
    def f(a, b, c):
        return a * b + c
    r1 = analyze_separability(f, ["a", "b", "c"], _R, mode="additive")
    r2 = analyze_separability(f, ["a", "b", "c"], _R, mode="additive")
    assert r1.groups == r2.groups
