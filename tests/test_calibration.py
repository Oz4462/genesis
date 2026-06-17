"""Confidence calibration — measure precision at a threshold, ECE, and consistency.

The accept threshold is chosen by measurement (lowest threshold meeting a precision bar,
maximising recall) and is honestly None when the labelled set cannot meet the bar; ECE is 0 for
a perfectly calibrated set and positive for an over-confident one; consistency confidence is the
agreement fraction across independent verdicts. Offline, no LLM, pure functions.

Run:  pytest tests/test_calibration.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from gen.calibration import (  # noqa: E402
    conformal_accept_threshold,
    conformal_quantile,
    consistency_confidence,
    expected_calibration_error,
    precision_recall_at,
    threshold_for_precision,
)

_SCORED = [(0.9, True), (0.8, True), (0.6, False), (0.4, True), (0.3, False)]


def test_precision_recall_at_a_threshold():
    op = precision_recall_at(_SCORED, 0.7)              # accept 0.9, 0.8 (both true)
    assert op.n_accepted == 2
    assert math.isclose(op.precision, 1.0)
    assert math.isclose(op.recall, 2 / 3)               # 2 of 3 true claims accepted


def test_threshold_for_precision_maximises_recall_at_the_bar():
    op = threshold_for_precision(_SCORED, target_precision=1.0)
    assert op is not None
    assert math.isclose(op.threshold, 0.8)              # lowest threshold holding precision 1.0
    assert math.isclose(op.precision, 1.0) and math.isclose(op.recall, 2 / 3)


def test_threshold_returns_none_when_the_bar_cannot_be_met():
    impossible = [(0.9, False), (0.5, True)]            # the top-confidence claim is false
    assert threshold_for_precision(impossible, target_precision=1.0) is None


def test_ece_zero_for_perfect_calibration_positive_for_overconfidence():
    perfect = [(1.0, True)] * 5 + [(0.0, False)] * 5    # confidence matches accuracy
    assert math.isclose(expected_calibration_error(perfect), 0.0, abs_tol=1e-12)
    overconfident = [(0.9, False)] * 10                 # 90% sure, 0% right
    assert math.isclose(expected_calibration_error(overconfident), 0.9, abs_tol=1e-9)


def test_consistency_confidence_is_the_agreement_fraction():
    assert consistency_confidence([True, True, True]) == 1.0          # unanimous
    assert math.isclose(consistency_confidence([True, True, False]), 2 / 3)
    assert consistency_confidence([True, False]) == 0.5               # a tie
    assert consistency_confidence([]) == 0.0


def test_is_deterministic():
    a = threshold_for_precision(_SCORED, 1.0)
    b = threshold_for_precision(_SCORED, 1.0)
    assert (a.threshold, a.precision, a.recall) == (b.threshold, b.precision, b.recall)


# --- split conformal: the distribution-free finite-sample guarantee ------------

def test_conformal_quantile_textbook_anchor():
    # n=9 scores 1..9, alpha=0.1: k = ceil(10*0.9) = 9 -> the 9th smallest = 9
    assert conformal_quantile([float(i) for i in range(1, 10)], 0.1) == 9.0
    # n=9, alpha=0.5: k = ceil(10*0.5) = 5 -> the 5th smallest = 5
    assert conformal_quantile([float(i) for i in range(1, 10)], 0.5) == 5.0


def test_conformal_quantile_refuses_when_set_too_small():
    # n=4, alpha=0.1: k = ceil(5*0.9) = 5 > 4 -> honest None, never an invented bound
    assert conformal_quantile([1.0, 2.0, 3.0, 4.0], 0.1) is None
    assert conformal_quantile([], 0.5) is None
    with pytest.raises(ValueError):
        conformal_quantile([1.0], 0.0)


def test_conformal_quantile_guarantee_holds_empirically():
    # exchangeable by construction: scores 1..100; the quantile must cover at
    # least (1-alpha) of a same-distribution sequence (finite-sample property)
    cal = [float(i) for i in range(1, 101)]
    q = conformal_quantile(cal, 0.2)
    covered = sum(1 for s in cal if s <= q) / len(cal)
    assert covered >= 0.8


def test_conformal_accept_threshold_lower_tail():
    # true-claim confidences, n=5, alpha=0.25: k = floor(0.25*6) = 1 -> smallest
    t = conformal_accept_threshold([0.5, 0.6, 0.7, 0.8, 0.9], 0.25)
    assert t == 0.5                                       # miss at most 25 percent
    # alpha=0.1 with n=5: k = floor(0.6) = 0 -> too few points, honest None
    assert conformal_accept_threshold([0.5, 0.6, 0.7, 0.8, 0.9], 0.1) is None
    with pytest.raises(ValueError):
        conformal_accept_threshold([0.5], 1.0)


def test_ece_does_not_misbin_a_negative_confidence_into_the_top_bin():
    # A c<0 must land in the LOW bin, not (via Python negative indexing) the TOP bin. The bug
    # merged -0.1 with the high-confidence pair in bin 9 and reported ~0.27; the correct binning
    # (-0.1 alone in bin 0, {0.95,0.96} in bin 9) gives ~0.337.
    ece = expected_calibration_error([(-0.1, False), (0.95, False), (0.96, True)], n_bins=10)
    assert ece > 0.30                                    # buggy top-bin merge gave 0.27


def test_threshold_for_precision_rejects_an_out_of_range_target():
    with pytest.raises(ValueError):
        threshold_for_precision(_SCORED, 1.5)            # >1 silently qualified nothing before
    with pytest.raises(ValueError):
        threshold_for_precision(_SCORED, -0.1)           # <0 silently qualified EVERYTHING before
