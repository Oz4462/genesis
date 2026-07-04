"""Tests for the trust-core CCDD drift monitor (optional `verify` extra).

Skips cleanly without trust-core. Proves the net-new capability GENESIS lacked:
a real distribution shift alerts, a no-shift stream stays quiet, and a degenerate
baseline is refused (honest, not silently "monitored").
"""

from __future__ import annotations

import numpy as np
import pytest

# Dotted on purpose: the PyPI 'trust-core' namesake ships no `conformal` — a bare
# importorskip("trust_core") would pass there and turn collection into an ERROR.
pytest.importorskip("trust_core.conformal.ccdd")

from gen.verification.drift_monitor import DriftMonitor  # noqa: E402


def _baseline(rng: np.random.Generator, n: int = 400, d: int = 8) -> np.ndarray:
    return rng.normal(0.0, 1.0, size=(n, d))


def test_alerts_on_real_shift():
    rng = np.random.default_rng(1)
    mon = DriftMonitor(_baseline(rng), window_size=100)
    stream = ((f"x{i}", rng.normal(1.5, 1.0, size=8)) for i in range(300))
    assert mon.scan(stream) is not None


def test_quiet_on_no_shift():
    rng = np.random.default_rng(2)
    mon = DriftMonitor(_baseline(rng), window_size=100)
    stream = ((f"x{i}", rng.normal(0.0, 1.0, size=8)) for i in range(300))
    assert mon.scan(stream) is None


def test_refuses_degenerate_baseline():
    with pytest.raises(ValueError):
        DriftMonitor(np.ones((400, 8)))  # zero-variance baseline -> refuse
    with pytest.raises(ValueError):
        DriftMonitor(np.zeros((10, 8)))  # too few calibration samples -> refuse
