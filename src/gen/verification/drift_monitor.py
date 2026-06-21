"""Model-output drift detection via trust-core CCDD (optional `verify` extra).

NET-NEW capability for GENESIS: detect when the generator/verifier model's output
distribution shifts away from a certified baseline, so an operator can re-verify
affected claims instead of trusting a silently-drifted model. PoV-4 proved this
fires on a real shift and stays quiet on a no-shift stream.

This wraps trust_core.conformal.ccdd (calibrate + StreamingDetector), which gives a
marginal per-window false-alarm-rate <= alpha_outer under exchangeability of the
calibration data. It is a MONITORING signal (opens a review), not a hard phase gate:
GENESIS RunState does not yet carry output embeddings, so wiring it into the phase
gates is deferred until embedding capture exists. Import is guarded so GENESIS core
stays numpy-only.
"""

from __future__ import annotations

import numpy as np

try:
    from trust_core.conformal.ccdd import StreamingDetector, calibrate
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "trust-core is required for gen.verification.drift_monitor. "
        "Install the optional extra: pip install -e '.[verify]'."
    ) from exc


class DriftMonitor:
    """Streaming drift monitor calibrated against baseline model-output embeddings."""

    def __init__(
        self,
        baseline_embeddings: np.ndarray,
        *,
        window_size: int = 100,
        alpha_inner: float = 0.05,
        alpha_outer: float = 0.01,
    ) -> None:
        """Calibrate against a 2-D ``(n, d)`` baseline (n >= 100) and arm the detector.

        Raises ``ValueError`` (from trust-core) on a degenerate or too-small baseline —
        an honest refusal to monitor rather than a false sense of coverage.
        """
        self._model = calibrate(np.asarray(baseline_embeddings, dtype=float))
        self._detector = StreamingDetector(
            self._model,
            window_size=window_size,
            alpha_inner=alpha_inner,
            alpha_outer=alpha_outer,
        )

    def observe(self, output_id: str, embedding: np.ndarray) -> None:
        """Score one new model-output embedding into the sliding window."""
        self._detector.observe(output_id, np.asarray(embedding, dtype=float))

    def check(self):
        """Return a ``DriftAlert`` if the current window meta-test fires, else ``None``."""
        return self._detector.check_alert()

    def scan(self, stream) -> int | None:
        """Feed an iterable of ``(output_id, embedding)`` and return the index of the
        first window that alerts, or ``None`` if no drift is detected."""
        for i, (output_id, embedding) in enumerate(stream):
            self.observe(output_id, embedding)
            if self.check() is not None:
                return i
        return None


__all__ = ["DriftMonitor"]
