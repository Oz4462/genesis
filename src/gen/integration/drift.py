"""Cross-run output-drift monitoring (Item 2a), wired via the integration layer.

GENESIS phase gates are deterministic and LLM-free by design, so model-output drift —
which needs an embedder and a CROSS-run baseline — does not belong in a phase gate. It
belongs in the monitoring layer: embed a run's output claim texts and test them against
a baseline distribution of prior runs' outputs with the CCDD `DriftMonitor` (Phase 1).
This module is that wiring; it stays opt-in (pulls the `verify` extra).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from ..verification.drift_monitor import DriftMonitor

Embedder = Callable[[str], np.ndarray]


def embed_texts(texts: Sequence[str], embedder: Embedder) -> np.ndarray:
    """Stack embeddings of texts into an ``(n, d)`` array (empty -> shape (0, 0))."""
    if not texts:
        return np.empty((0, 0))
    return np.vstack([np.asarray(embedder(t), dtype=float) for t in texts])


def detect_run_drift(
    claim_texts: Sequence[str],
    embedder: Embedder,
    baseline_embeddings: np.ndarray,
    *,
    window_size: int = 100,
    alpha_inner: float = 0.05,
    alpha_outer: float = 0.01,
) -> tuple[bool, int | None]:
    """Test a run's output claim texts for drift vs a baseline of prior outputs.

    Returns ``(alerted, first_alert_index)``. The baseline must hold >= 100 prior
    output embeddings (CCDD calibration floor) — an operator accumulates these across
    runs; a single run rarely drifts on its own, which is exactly why this is a
    cross-run monitor, not a per-run gate. Raises (via DriftMonitor/calibrate) on a
    degenerate or too-small baseline rather than feigning coverage.
    """
    monitor = DriftMonitor(
        baseline_embeddings,
        window_size=window_size,
        alpha_inner=alpha_inner,
        alpha_outer=alpha_outer,
    )
    stream = ((f"claim-{i}", embedder(t)) for i, t in enumerate(claim_texts))
    idx = monitor.scan(stream)
    return (idx is not None), idx


__all__ = ["embed_texts", "detect_run_drift"]
