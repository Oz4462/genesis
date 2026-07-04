"""Model-output drift detection via trust-core CCDD (optional `verify` extra).

NET-NEW capability for GENESIS: detect when the generator/verifier model's output
distribution shifts away from a certified baseline, so an operator can re-verify
affected claims instead of trusting a silently-drifted model. PoV-4 proved this
fires on a real shift and stays quiet on a no-shift stream.

This wraps trust_core.conformal.ccdd (calibrate + StreamingDetector), which gives a
marginal per-window false-alarm-rate <= alpha_outer under exchangeability of the
calibration data. It is a MONITORING signal (opens a review), never a phase gate:
GENESIS phase gates are deterministic and LLM-free by design. The run-level wiring
EXISTS as `gen.integration.drift.detect_run_drift` (embeds a run's output claim
texts, tests them against a baseline of prior runs); wiring that into the run
composition (`gen.integration.audited_run` hook + visible result field) stays
OWNER-GATED because an honest hook is not yet provable offline (audited 2026-07-04):
  (i)  no cross-run baseline store exists — CCDD calibration needs >= 100 output
       embeddings accumulated from REAL prior runs, which no module persists yet;
  (ii) the production embedder is a live local model call
       (`gen.memory.ollama_embedder`); a hash/toy embedder cannot see semantic
       drift, so monitoring with it would be fake coverage;
  (iii) the real trust-core is a private companion library (the PyPI 'trust-core'
       is an unrelated namesake, see the guard below), so a wiring test cannot run
       in the sandboxed dev environment — it would be a permanently-skipped test.
Import is guarded so GENESIS core stays numpy-only.
"""

from __future__ import annotations

import numpy as np

try:
    from trust_core.conformal.ccdd import StreamingDetector, calibrate
except ImportError as exc:  # tested via tests/test_verify_extra_seam.py
    raise ImportError(
        "gen.verification.drift_monitor needs trust_core.conformal.ccdd from the "
        "REAL trust-core companion library (private sibling repo, see "
        "docs/integration/PHASE1_TRUSTCORE.md). The 'trust-core' package on PyPI "
        "is an unrelated namesake WITHOUT this module — do not install it from "
        "PyPI. Install the companion library instead: "
        "pip install -e <path-to>/trust-core."
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
