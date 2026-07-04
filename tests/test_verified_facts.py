"""Tests for the cross-run verified-facts memory (gen.memory).

Offline + deterministic: a controlled basis-vector embedder makes exact repeats
score ~0 and unrelated queries orthogonal (score ~1), so the conformal honesty gate
is exercised without Ollama. (The real-embedder honesty proof is PoV-2.)
"""

from __future__ import annotations

import numpy as np

from gen.core.state import Claim, ClaimStatus, SourceRef
from gen.memory import VerifiedFactsLibrary

_BASIS = {
    "standard gravity is 9.80665 m/s^2": 0,
    "speed of light is 299792458 m/s": 1,
    "M4 screw nominal diameter is 4 mm": 2,
    "unrelated nonsense about glubbex polymer": 7,
}


def _embedder():
    def embed(text: str) -> np.ndarray:
        v = np.zeros(8, dtype=np.float64)
        v[_BASIS.get(text, 6)] = 1.0  # unknown texts collapse to a shared axis
        return v

    return embed


def _claim(cid: str, text: str, status: ClaimStatus) -> Claim:
    return Claim(
        id=cid,
        text=text,
        sources=[SourceRef(url_or_id=f"src://{cid}", retrieved=True)],
        status=status,
    )


def _lib() -> VerifiedFactsLibrary:
    lib = VerifiedFactsLibrary(_embedder(), alpha=0.1)
    lib.remember(
        [
            _claim("c0", "standard gravity is 9.80665 m/s^2", ClaimStatus.VERIFIED),
            _claim("c1", "speed of light is 299792458 m/s", ClaimStatus.VERIFIED),
            _claim("c2", "M4 screw nominal diameter is 4 mm", ClaimStatus.VERIFIED),
            _claim("c3", "an UNVERIFIED guess", ClaimStatus.UNVERIFIED),
        ]
    )
    return lib


def test_only_verified_claims_are_stored():
    lib = _lib()
    assert lib.n_facts == 3  # the UNVERIFIED claim was not deposited


def test_abstains_before_calibration():
    lib = _lib()
    assert not lib.calibrated
    assert lib.recall("standard gravity is 9.80665 m/s^2").abstained


def test_recalls_exact_repeat_after_calibration():
    lib = _lib()
    lib.add_calibration([1e-6] * 40)  # genuine-match scores ~0 -> small tau
    assert lib.calibrated
    res = lib.recall("standard gravity is 9.80665 m/s^2")
    assert not res.abstained
    assert res.accepted[0].claim_id == "c0"
    assert res.accepted[0].score <= (res.tau or 0.0)


def test_abstains_on_unrelated_query():
    lib = _lib()
    lib.add_calibration([1e-6] * 40)
    res = lib.recall("unrelated nonsense about glubbex polymer")
    assert res.abstained  # orthogonal -> score ~1 -> above tau -> no false reuse


def test_remember_deduplicates_by_capture_id_across_calls():
    # Re-running the same (reproducible) run re-produces the same claim id; a second
    # deposit must NOT create a duplicate step (duplicate steps = recall noise).
    lib = _lib()
    again = lib.remember([_claim("c0", "standard gravity is 9.80665 m/s^2", ClaimStatus.VERIFIED)])
    assert again == 0
    assert lib.n_facts == 3


def test_remember_deduplicates_within_one_call():
    lib = VerifiedFactsLibrary(_embedder(), alpha=0.1)
    c = _claim("c0", "standard gravity is 9.80665 m/s^2", ClaimStatus.VERIFIED)
    assert lib.remember([c, c]) == 1
    assert lib.n_facts == 1
