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

from gen.calibration import (  # noqa: E402
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
