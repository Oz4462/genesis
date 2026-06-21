"""Item 2 tests: cross-run drift monitoring (2a) + memory recall prefilter (2b).

Skips without the `verify` extra (trust-core). Offline + deterministic.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

pytest.importorskip("trust_core")

from gen.core.state import Claim, ClaimStatus, SourceRef  # noqa: E402
from gen.integration.drift import detect_run_drift  # noqa: E402
from gen.memory import VerifiedFactsLibrary  # noqa: E402


# --- 2a: cross-run drift ------------------------------------------------------
def _vec_embedder(shift: float = 0.0):
    # deterministic per-text vector drawn around `shift` (seeded by the text)
    def embed(text: str) -> np.ndarray:
        h = int(hashlib.sha256(text.encode()).hexdigest(), 16) % 100000
        return np.random.default_rng(h).normal(shift, 1.0, size=8)
    return embed


def test_drift_detects_shifted_run_outputs():
    rng = np.random.default_rng(1)
    baseline = rng.normal(0.0, 1.0, size=(400, 8))           # prior runs' outputs
    shifted_texts = [f"claim {i}" for i in range(300)]
    alerted, _idx = detect_run_drift(shifted_texts, _vec_embedder(shift=1.5), baseline)
    assert alerted is True


def test_drift_quiet_on_in_distribution_run():
    rng = np.random.default_rng(2)
    baseline = rng.normal(0.0, 1.0, size=(400, 8))
    texts = [f"claim {i}" for i in range(300)]
    alerted, _idx = detect_run_drift(texts, _vec_embedder(shift=0.0), baseline)
    assert alerted is False


# --- 2b: recall prefilter carries provenance ----------------------------------
def _embedder():
    def embed(text: str) -> np.ndarray:
        h = hashlib.sha256(text.encode()).digest()
        return np.frombuffer(h[:32], dtype=np.uint8).astype(np.float64)
    return embed


def test_recall_returns_fact_with_provenance():
    lib = VerifiedFactsLibrary(_embedder(), alpha=0.1)
    claim = Claim(
        id="c0", text="standard gravity is 9.80665 m/s^2",
        sources=[SourceRef(url_or_id="https://src/grav", retrieved=True)],
        status=ClaimStatus.VERIFIED,
    )
    assert lib.remember([claim]) == 1
    lib.add_calibration([1e-6] * 40)
    res = lib.recall("standard gravity is 9.80665 m/s^2")
    assert not res.abstained
    fact = res.accepted[0]
    assert fact.claim_id == "c0"
    assert fact.sources == ("https://src/grav",)  # provenance preserved across runs
