"""Tests for the trust-core verification adapter (optional `verify` extra).

Skips cleanly when trust-core is not installed, preserving GENESIS's numpy-only
offline-core guarantee. The decisive test is the EQUIVALENCE PIN: the adapter's
split-conformal threshold must equal the numpy-only `gen.calibration.conformal_quantile`
across many cases, so the two can never silently diverge (single behaviour, one
source of truth at runtime when the extra is present).
"""

from __future__ import annotations

import random

import pytest

# Dotted on purpose: the PyPI 'trust-core' namesake ships neither `conformal` nor
# `math.fdr` — a bare importorskip("trust_core") would pass there and turn
# collection into an ERROR.
pytest.importorskip("trust_core.conformal.split")
pytest.importorskip("trust_core.math.fdr")

from gen.calibration import conformal_quantile  # noqa: E402
from gen.verification import trustcore_adapter as tca  # noqa: E402


def test_split_conformal_equivalence_pin():
    rng = random.Random(20260613)
    for _ in range(2000):
        n = rng.randint(1, 40)
        scores = [rng.gauss(0, 1) for _ in range(n)]
        alpha = rng.uniform(0.01, 0.5)
        g = conformal_quantile(scores, alpha)
        t = tca.split_conformal_threshold(scores, alpha)
        if g is None:
            assert t is None
        else:
            assert t is not None and abs(g - t) <= 1e-12


def test_split_conformal_none_and_value_conventions():
    assert tca.split_conformal_threshold([], 0.5) is None          # empty -> None
    assert tca.split_conformal_threshold([1.0, 2.0, 3.0, 4.0], 0.1) is None  # k>n -> None
    # textbook anchor (matches calibration.conformal_quantile)
    assert tca.split_conformal_threshold([float(i) for i in range(1, 10)], 0.1) == 9.0
    with pytest.raises(ValueError):
        tca.split_conformal_threshold([1.0], 0.0)


def test_bh_fdr_threshold_basic():
    # one tiny p-value among large ones -> BH rejects it; cutoff >= that p.
    p = [0.001, 0.4, 0.5, 0.6, 0.9]
    cut = tca.bh_fdr_threshold(p, 0.05)
    assert cut >= 0.001
    # nothing significant -> cutoff 0.0
    assert tca.bh_fdr_threshold([0.9, 0.95, 0.99], 0.05) == 0.0
    with pytest.raises(ValueError):
        tca.bh_fdr_threshold([0.1], 1.0)


def test_bh_adjusted_qvalues_monotone_and_bounded():
    q = tca.bh_adjusted_qvalues([0.001, 0.01, 0.2, 0.8])
    assert len(q) == 4
    assert all(0.0 <= v <= 1.0 for v in q)
