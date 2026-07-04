"""Adapter onto `trust-core` verification math (optional `verify` extra).

GENESIS depends on `trust-core` for the conformal / FDR primitives instead of
re-deriving them: PoV-1 proved `trust_core.conformal.split.split_conformal_threshold`
is byte-identical to GENESIS's own split-conformal quantile (0 mismatch / 5000 cases),
and `trust-core` additionally ships FDR control + CCDD drift detection that GENESIS
lacked. `trust-core` is a thin, dual-licensed (Apache-2.0 OR MIT) library that VERIDEX
already consumes; installing it editable makes it the single source of truth for this
math (no duplicated implementation in `src/gen`).

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
except ImportError as exc:  # tested via tests/test_verify_extra_seam.py
    raise ImportError(
        "gen.verification.trustcore_adapter needs trust_core.conformal.split and "
        "trust_core.math.fdr from the REAL trust-core companion library (private "
        "sibling repo, see docs/integration/PHASE1_TRUSTCORE.md). The 'trust-core' "
        "package on PyPI is an unrelated namesake WITHOUT these modules — do not "
        "install it from PyPI. Install the companion library instead: "
        "pip install -e <path-to>/trust-core."
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
