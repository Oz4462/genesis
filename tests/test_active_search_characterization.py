"""Characterization test: active_search implements genuine InfoBAX uncertainty sampling.

Audit target — ``gen.discovery.active_search`` claims to drive evaluation ORDER by
binary entropy / expected information gain (InfoBAX), never by raw iteration or index.
The gate remains the sole oracle. This file proves the headline is earned, not a facade:

  1. binary_entropy peaks at exactly 1.0 for p=0.5 and is 0.0 for certain outcomes (p=0/1).
  2. PassModel on empty history returns 0.5 (max uncertainty); with gated examples it
     returns an inverse-distance-weighted probability that moves toward the label of
     a nearby example.
  3. select_most_informative returns the index of highest EIG; ties break to the
     lowest index (deterministic).
  4. active_select honors budget exactly (gate_calls == min(budget, n)), stops early
     on exhausted pool, is byte-deterministic for identical runs, and the gating ORDER
     genuinely depends on features+labels (a constructed case where uniform sequential
     baseline would have gated a different candidate at the same step).
  5. Negative contract: budget < 0 raises ValueError with the documented message.

These properties are the standing proof that selection is entropy-driven. Deterministic.
No source edits were required — the implementation already satisfies the contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.discovery.active_search import (
    ActiveResult,
    PassModel,
    active_select,
    binary_entropy,
    select_most_informative,
)


# --- binary_entropy properties -----------------------------------------------------------

def test_binary_entropy_peaks_at_one_half_and_zero_at_extremes():
    assert binary_entropy(0.5) == 1.0
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(1.0) == 0.0
    # strictly between
    assert binary_entropy(0.5) > binary_entropy(0.25) > binary_entropy(0.02) > 0.0


@settings(deadline=None, derandomize=True, max_examples=50)
@given(p=st.floats(min_value=0.0, max_value=1.0))
def test_binary_entropy_invariant_bounds_and_symmetry(p: float):
    """PROPERTY: entropy always [0,1], symmetric, max only at 0.5 (within float tolerance)."""
    e = binary_entropy(p)
    assert 0.0 <= e <= 1.0
    # symmetry
    assert abs(e - binary_entropy(1.0 - p)) < 1e-12
    # only 0.5 (or boundaries) can reach 1.0; near 0.5 is close to 1
    if 1e-9 < p < 1.0 - 1e-9:
        # strict interior
        if abs(p - 0.5) < 1e-9:
            assert abs(e - 1.0) < 1e-12
        else:
            assert e < 1.0


# --- PassModel -----------------------------------------------------------------------

def test_pass_model_empty_history_max_uncertainty():
    """Empty history -> predict 0.5 for any feature (max uncertainty, start of InfoBAX)."""
    model = PassModel([])
    assert model.predict((0.0,)) == 0.5
    assert model.predict((42.0, 17.0)) == 0.5
    assert model.expected_information_gain((0.0,)) == 1.0


def test_pass_model_inverse_distance_weighted_moves_toward_label():
    """On gated examples, predict is IDW and moves toward the label of a nearby point."""
    # Two antipodal examples: pass at 0, fail at 10.
    gated = [((0.0,), True), ((10.0,), False)]
    model = PassModel(gated)
    # near pass example -> high p
    assert model.predict((0.1,)) > 0.98
    # near fail -> low p
    assert model.predict((9.9,)) < 0.02
    # exact match on a gated point yields (numerically) the label; safeguard 1e-9 makes it extremely close to 0/1, not bitwise exact
    assert model.predict((0.0,)) > 0.999999
    assert model.predict((10.0,)) < 0.000001
    # midpoint -> ~0.5 (max uncertainty)
    mid_p = model.predict((5.0,))
    assert abs(mid_p - 0.5) < 1e-6
    assert model.expected_information_gain((5.0,)) > 0.99
    # closer to pass than fail -> p > 0.5
    assert model.predict((3.0,)) > model.predict((7.0,))


# --- select_most_informative ---------------------------------------------------------

def test_select_most_informative_picks_highest_eig_and_lowest_index_on_tie():
    model = PassModel([((0.0,), True), ((10.0,), False)])
    feats = [(0.0,), (5.0,), (10.0,)]
    # 5.0 has highest entropy (~0.5), endpoints certain
    assert select_most_informative(feats, model) == 1

    # All same EIG (after single label): must pick lowest index (0)
    model_one = PassModel([((0.0,), True)])
    feats2 = [(0.0,), (1.0,), (2.0,)]
    assert select_most_informative(feats2, model_one) == 0

    # Explicit tie among equal-EIG later indices: still lowest index wins
    # (all EIG=0 here)
    assert select_most_informative([(10.0,), (20.0,)], model_one) == 0


# --- active_select contract ----------------------------------------------------------

def test_active_select_honors_budget_and_stops_on_exhaustion():
    pool = list(range(5))
    def gate(x: int) -> bool:
        return x == 3
    def feature(x: int) -> tuple[float, ...]:
        return (float(x),)

    # budget < len
    r1 = active_select(pool, gate, feature, budget=2)
    assert r1.gate_calls == 2
    assert len(r1.gated) == 2

    # budget > len -> stops early at len
    r2 = active_select(pool, gate, feature, budget=99)
    assert r2.gate_calls == len(pool) == 5
    assert len(r2.gated) == 5

    # budget=0 -> zero calls, empty
    r0 = active_select(pool, gate, feature, budget=0)
    assert r0.gate_calls == 0
    assert r0.gated == ()
    assert r0.passing == ()


def test_active_select_is_deterministic():
    pool = [10, 20, 30, 40, 50]
    def gate(x: int) -> bool:
        return x > 25
    def feature(x: int) -> tuple[float, ...]:
        return (float(x),)
    a = active_select(pool, gate, feature, budget=3)
    b = active_select(pool, gate, feature, budget=3)
    assert a.gated == b.gated
    assert a.passing == b.passing
    assert a.gate_calls == b.gate_calls
    assert isinstance(a, ActiveResult)


def test_active_select_negative_budget_raises():
    """NEGATIVE: budget<0 must fail loud with exact message (no silent default)."""
    with pytest.raises(ValueError, match="budget must be >= 0"):
        active_select([1, 2], lambda x: True, lambda x: (float(x),), budget=-1)


def test_active_select_order_depends_on_features_and_labels_not_iteration():
    """The gating order is driven by EIG (binary entropy of predict), not by list order.

    Constructed case: after the first two (forced by initial all-tie + lowest-index),
    the third candidate chosen is index 3 (highest EIG at the uncertainty peak between
    the mixed labels), whereas a uniform-iteration baseline would have chosen 2 next.
    This proves features+labels actually steer the selection.
    """
    cands = [0, 1, 2, 3]
    # Features deliberately placed so mid-point (high uncertainty) is at higher index.
    feat_map = {0: (0.0,), 1: (100.0,), 2: (1.0,), 3: (50.0,)}
    def feature(c: int) -> tuple[float, ...]:
        return feat_map[c]

    def gate(c: int) -> bool:
        # 0=False (at 0), 1=True (at 100) -> after gating these two we have mixed labels
        # 2 close to 0 (predict ~0, low EIG), 3 mid (predict~0.5, high EIG=1)
        return c == 1

    res = active_select(cands, gate, feature, budget=3)
    gated_cands = [c for c, _ in res.gated]
    assert res.gate_calls == 3
    assert gated_cands[0] == 0
    assert gated_cands[1] == 1
    # The key non-sequential step: 3 before 2 because of EIG after mixed labels.
    assert gated_cands[2] == 3, f"expected entropy-driven pick of 3, got order {gated_cands}"
    # Uniform baseline prefix of length 3 would have been [0,1,2]
    assert gated_cands != [0, 1, 2]

    # Double-check the EIGs that drove the decision (after gating 0+1)
    model = PassModel([(feat_map[0], False), (feat_map[1], True)])
    e2 = model.expected_information_gain(feat_map[2])
    e3 = model.expected_information_gain(feat_map[3])
    assert e3 > e2
    assert abs(e3 - 1.0) < 1e-9  # peak uncertainty


def test_active_select_passing_set_only_contains_gate_true():
    """The .passing tuple contains exactly those the real gate returned True for."""
    pool = list(range(6))
    def gate(x: int) -> bool:
        return x % 2 == 0
    def feature(x: int) -> tuple[float, ...]:
        return (float(x),)
    res = active_select(pool, gate, feature, budget=5)
    for cand, passed in res.gated:
        assert (cand in res.passing) == passed
    assert all(gate(c) for c in res.passing)


# --- End of characterization (no source change needed; implementation is REAL) ---
