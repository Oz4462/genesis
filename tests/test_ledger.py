"""Tests for the ledger — proving provenance enforcement WITHOUT any LLM or DB.

These exercise the InMemoryLedgerStore, the canonical reference implementation
(the Postgres adapter enforces the identical invariants via sql/001_ledger.sql).
They cover Aufgabe 1 of CLAUDE_CODE_AUFTRAG_001:

  * mandatory provenance (layer 2: the store re-checks, not just the constructor)
  * append-only creation (duplicate id rejected)
  * loud failure on updating an unknown claim
  * fetch recording (dead-citation detection input)
  * the independence rule (mirror of v_non_independent_verifications)
  * batch atomicity (a bad claim leaves no partial state)
  * determinism / reproducibility (stable ordering -> identical snapshots, A5)
"""

from __future__ import annotations

import asyncio
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import UnsourcedClaimError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    SourceRef,
    SourceSupport,
)
from gen.ledger.store import (  # noqa: E402
    InMemoryLedgerStore,
    UnknownClaimError,
)


def run(coro):
    """Run an async coroutine in a fresh event loop (no plugin dependency)."""
    return asyncio.run(coro)


def _src(url: str, retrieved: bool = True) -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=retrieved, support=SourceSupport.SUPPORTS)


def _claim(cid: str, text: str = "fact", url: str = "https://a.example") -> Claim:
    return Claim(id=cid, text=text, sources=[_src(url)], produced_by="scholar")


# --- Mandatory provenance (layer 2) ------------------------------------------

def test_add_rejects_claim_whose_sources_were_emptied():
    """Layer 2: even a once-valid claim is rejected if its sources are emptied.

    The constructor (layer 1) cannot catch this, because `sources` is mutable
    and may be cleared after construction. The store must re-check.
    """
    store = InMemoryLedgerStore()
    c = _claim("c1")
    c.sources = []  # simulate post-construction tampering
    with pytest.raises(UnsourcedClaimError):
        run(store.add_claims("r1", [c]))
    # And nothing was persisted.
    assert run(store.get_claims("r1")) == []


def test_add_and_get_roundtrip_in_insertion_order():
    store = InMemoryLedgerStore()
    run(store.add_claims("r1", [_claim("c1"), _claim("c2"), _claim("c3")]))
    got = run(store.get_claims("r1"))
    assert [c.id for c in got] == ["c1", "c2", "c3"]


def test_duplicate_claim_id_is_rejected():
    store = InMemoryLedgerStore()
    run(store.add_claims("r1", [_claim("c1")]))
    with pytest.raises(ValueError):
        run(store.add_claims("r1", [_claim("c1")]))


# --- Updates fail loudly -----------------------------------------------------

def test_update_unknown_claim_raises():
    store = InMemoryLedgerStore()
    with pytest.raises(UnknownClaimError):
        run(store.update_claim(_claim("ghost")))


def test_update_persists_status_and_confidence():
    store = InMemoryLedgerStore()
    run(store.add_claims("r1", [_claim("c1")]))
    [c] = run(store.get_claims("r1"))
    c.status = ClaimStatus.VERIFIED
    c.confidence = 0.91
    c.verification = [SourceRef(
        url_or_id="https://independent.example",
        retrieved=True,
        support=SourceSupport.SUPPORTS,
    )]
    run(store.update_claim(c))
    [again] = run(store.get_claims("r1"))
    assert again.status is ClaimStatus.VERIFIED
    assert again.confidence == 0.91
    assert again.verification[0].url_or_id == "https://independent.example"


def test_update_that_empties_sources_raises():
    store = InMemoryLedgerStore()
    run(store.add_claims("r1", [_claim("c1")]))
    [c] = run(store.get_claims("r1"))
    c.sources = []
    with pytest.raises(UnsourcedClaimError):
        run(store.update_claim(c))


# --- Fetch recording (input to DEAD_CITATION detection) ----------------------

def test_record_and_get_fetch():
    store = InMemoryLedgerStore()
    run(store.record_fetch("r1", "https://ok.example", True, "deadbeef"))
    run(store.record_fetch("r1", "https://bad.example", False, None))
    ok = run(store.get_fetch("r1", "https://ok.example"))
    bad = run(store.get_fetch("r1", "https://bad.example"))
    assert ok.ok is True and ok.content_hash == "deadbeef"
    assert bad.ok is False and bad.content_hash is None
    assert run(store.get_fetch("r1", "https://never.example")) is None


# --- Independence rule (PHASE_ALPHA §3.4) ------------------------------------

def test_independence_violation_is_detected():
    """A skeptic source reusing a scholar URL for the same claim is a violation."""
    store = InMemoryLedgerStore()
    c = Claim(
        id="c1",
        text="fact",
        sources=[_src("https://shared.example")],     # scholar source
        produced_by="scholar",
    )
    c.verification = [_src("https://shared.example")]  # skeptic REUSES it -> bad
    run(store.add_claims("r1", [c]))
    assert store.non_independent_verifications("r1") == [("c1", "https://shared.example")]


def test_independent_verification_is_clean():
    store = InMemoryLedgerStore()
    c = Claim(
        id="c1",
        text="fact",
        sources=[_src("https://scholar.example")],
        produced_by="scholar",
    )
    c.verification = [_src("https://independent.example")]  # genuinely new
    run(store.add_claims("r1", [c]))
    assert store.non_independent_verifications("r1") == []


# --- Batch atomicity ---------------------------------------------------------

def test_bad_claim_in_batch_leaves_no_partial_state():
    """If any claim in a batch is invalid, none of the batch is persisted."""
    store = InMemoryLedgerStore()
    good = _claim("c1")
    bad = _claim("c2")
    bad.sources = []
    with pytest.raises(UnsourcedClaimError):
        run(store.add_claims("r1", [good, bad]))
    assert run(store.get_claims("r1")) == []  # 'good' was NOT half-written


# --- Determinism / reproducibility (A5) --------------------------------------

def test_identical_inputs_yield_identical_snapshots():
    """Same claims in the same order -> identical stored order and values."""
    base = [_claim("c1", "a"), _claim("c2", "b"), _claim("c3", "c")]

    store_a = InMemoryLedgerStore()
    run(store_a.add_claims("r1", copy.deepcopy(base)))

    store_b = InMemoryLedgerStore()
    run(store_b.add_claims("r1", copy.deepcopy(base)))

    a = run(store_a.get_claims("r1"))
    b = run(store_b.get_claims("r1"))
    def key(cs):
        return [(c.id, c.text, c.status.value, c.confidence) for c in cs]
    assert key(a) == key(b)
    assert [c.id for c in a] == ["c1", "c2", "c3"]
