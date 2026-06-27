"""Adapter onto `trust-core` verification math (OPTIONAL `verify` extra).

HONEST SCOPE (corrected 2026-06-28): GENESIS does NOT depend on `trust-core`. The default,
always-present implementation of the split-conformal quantile lives in `gen.calibration.
conformal_quantile` and is the single source of truth for core runs; `trust-core` is a private,
optional library (not on PyPI, not installed by default) and this adapter is imported ONLY by
callers that opt into the `verify` extra. So a duplicate implementation DOES exist by design —
the built-in is canonical; this adapter is a parity bridge, not a dependency. PoV-1 proved
`trust_core.conformal.split.split_conformal_threshold` is byte-identical to the built-in
(0 mismatch / 5000 cases); `trust-core` additionally ships FDR control + CCDD drift detection
that the built-in does not. When the extra is absent, importing this module raises a clear error
(below) — it never silently swaps the math.

This adapter keeps GENESIS's honesty conventions at the boundary:
  * an under-sized calibration set returns ``None`` (honest abstention), never an
    invented bound — trust-core signals the same case with ``+inf``, mapped here.

Import is guarded: GENESIS core stays numpy-only; only callers that opt into the
`verify` extra import this module.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

try:
    from trust_core.conformal.split import (
        split_conformal_threshold as _tc_split_conformal_threshold,
    )
    from trust_core.math.fdr import bh_adjusted as _tc_bh_adjusted
    from trust_core.math.fdr import bh_threshold as _tc_bh_threshold
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "trust-core is required for gen.verification.trustcore_adapter. "
        "Install the optional extra: pip install -e '.[verify]' "
        "(or: pip install -e <path-to>/trust-core)."
    ) from exc


def split_conformal_threshold(scores: Sequence[float], alpha: float) -> float | None:
    """Split-conformal upper quantile via trust-core, in GENESIS's None-convention.

    Returns the ceil((n+1)(1-alpha))-th order statistic of ``scores``; returns
    ``None`` when the calibration set is empty or too small for the requested
    alpha (the case trust-core reports as ``+inf``). Raises ``ValueError`` on
    ``alpha`` outside (0, 1). Numerically identical to the former
    ``gen.calibration.conformal_quantile`` body (PoV-1: 0 mismatch / 5000).
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    if len(scores) == 0:
        return None
    thr = _tc_split_conformal_threshold(scores, alpha)
    return None if thr == math.inf else float(thr)


def bh_fdr_threshold(p_values: Sequence[float], alpha: float) -> float:
    """Benjamini-Hochberg cutoff p_(k*) at false-discovery rate ``alpha``.

    Net-new for GENESIS: lets a gate accept a BATCH of m candidate claims while
    bounding the expected false-discovery fraction at ``alpha`` (vs thresholding
    each claim independently). Returns 0.0 when nothing is rejected — callers that
    must distinguish "nothing rejected" from "rejected at p=0" should use the
    q-values from :func:`bh_adjusted_qvalues`. Source: Benjamini & Hochberg (1995).
    """
    return float(_tc_bh_threshold(p_values, alpha))


def bh_adjusted_qvalues(p_values: Sequence[float]) -> list[float]:
    """BH-adjusted q-values (one per input p-value, input order). Net-new."""
    return list(_tc_bh_adjusted(p_values))


__all__ = ["split_conformal_threshold", "bh_fdr_threshold", "bh_adjusted_qvalues"]
