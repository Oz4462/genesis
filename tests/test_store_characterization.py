"""Characterization + hardening audit for ``InMemoryLedgerStore``.

Depth-audit (T03): pin the documented invariants of ``src/gen/ledger/store.py``
as executable contracts so a regression turns red instead of drifting silently.
These complement the legacy ``test_ledger.py``; they intentionally re-assert the
same invariants from an independent angle (insertion-order determinism, batch
atomicity, deep-copy isolation, fetch idempotency, the independence rule) plus a
property-based ordering invariant (Hypothesis).

No LLM, no DB, no network: the InMemory store is the canonical reference
implementation, and every guard here is a pure in-process check.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import UnsourcedClaimError  # noqa: E402
from gen.core.state import (  # noqa: E402
    Claim,
    ClaimStatus,
    SourceRef,
    SourceSupport,
)
from gen.ledger.store import (  # noqa: E402
    FetchRecord,
    InMemoryLedgerStore,
    UnknownClaimError,
)

RUN = "run-1"


def run(coro):
    """Drive a coroutine in a fresh event loop (no pytest-asyncio dependency).

    Mirrors the legacy test helper so this file is self-contained and passes in
    a worktree that carries only its own files plus pre-existing repo code.
    """
    return asyncio.run(coro)


def _src(url: str, retrieved: bool = True) -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=retrieved, support=SourceSupport.SUPPORTS)


def _claim(cid: str, text: str = "fact", url: str = "https://a.example") -> Claim:
    return Claim(id=cid, text=text, sources=[_src(url)], produced_by="scholar")


# --- Persistence + insertion-order determinism (A5) --------------------------

def test_add_then_get_preserves_insertion_order():
    """get_claims returns claims in the exact order they were added (A5)."""
    store = InMemoryLedgerStore()
    ids = ["c3", "c1", "c2"]  # deliberately NOT sorted, to prove it is not sorting
    run(store.add_claims(RUN, [_claim(c) for c in ids]))
    assert [c.id for c in run(store.get_claims(RUN))] == ids


def test_get_claims_unknown_run_is_empty():
    """A run with no claims yields an empty list, not a KeyError."""
    store = InMemoryLedgerStore()
    assert run(store.get_claims("never-seen")) == []


def test_identical_op_sequence_yields_identical_snapshot():
    """Determinism: two stores driven by the same ops produce equal snapshots."""
    def build() -> InMemoryLedgerStore:
        store = InMemoryLedgerStore()
        run(store.add_claims(RUN, [_claim("c1"), _claim("c2")]))
        updated = _claim("c1")
        updated.status = ClaimStatus.VERIFIED
        updated.confidence = 0.9
        run(store.update_claim(updated))
        return store

    snap_a = build().snapshot(RUN)
    snap_b = build().snapshot(RUN)
    assert [c.id for c in snap_a] == [c.id for c in snap_b]
    assert [(c.status, c.confidence) for c in snap_a] == [
        (c.status, c.confidence) for c in snap_b
    ]


@settings(max_examples=50)
@given(st.lists(st.text(min_size=1, max_size=8), min_size=0, max_size=12, unique=True))
def test_property_get_claims_round_trips_insertion_order(ids):
    """Invariant: for ANY sequence of unique ids, get_claims echoes that order.

    A property test (not just hand-picked ids) because insertion-order
    determinism must hold across the whole id space, including the empty batch.
    """
    store = InMemoryLedgerStore()
    run(store.add_claims(RUN, [_claim(cid) for cid in ids]))
    assert [c.id for c in run(store.get_claims(RUN))] == ids


# --- Mandatory provenance + batch atomicity (no partial write) ---------------

def test_add_rejects_unsourced_claim_layer2():
    """Layer 2: a claim emptied AFTER construction is still rejected by the store."""
    store = InMemoryLedgerStore()
    bad = _claim("c1")
    bad.sources = []  # sources is a mutable list; constructor (layer 1) cannot catch this
    with pytest.raises(UnsourcedClaimError):
        run(store.add_claims(RUN, [bad]))


def test_bad_claim_in_batch_rejects_whole_batch_atomically():
    """A good claim batched with an unsourced one leaves the ledger UNCHANGED."""
    store = InMemoryLedgerStore()
    good = _claim("good")
    bad = _claim("bad")
    bad.sources = []
    with pytest.raises(UnsourcedClaimError):
        run(store.add_claims(RUN, [good, bad]))
    # Atomicity: neither claim was written — validation precedes all mutation.
    assert run(store.get_claims(RUN)) == []


def test_duplicate_in_batch_with_existing_rejects_atomically():
    """A duplicate id batched with a fresh claim rejects the batch with no partial write."""
    store = InMemoryLedgerStore()
    run(store.add_claims(RUN, [_claim("c1")]))
    with pytest.raises(ValueError):
        run(store.add_claims(RUN, [_claim("fresh"), _claim("c1")]))
    # 'fresh' must NOT have been persisted by the partially-processed batch.
    assert [c.id for c in run(store.get_claims(RUN))] == ["c1"]


def test_add_rejects_duplicate_claim_id():
    """Creation is append-only: re-adding an existing id raises ValueError."""
    store = InMemoryLedgerStore()
    run(store.add_claims(RUN, [_claim("c1")]))
    with pytest.raises(ValueError):
        run(store.add_claims(RUN, [_claim("c1")]))


# --- update_claim guards -----------------------------------------------------

def test_update_unknown_claim_raises_loud():
    """Updating a never-added id fails loud (UnknownClaimError), not silent insert."""
    store = InMemoryLedgerStore()
    with pytest.raises(UnknownClaimError):
        run(store.update_claim(_claim("ghost")))


def test_update_sourceless_claim_rejected():
    """An update that would leave the claim sourceless is rejected."""
    store = InMemoryLedgerStore()
    run(store.add_claims(RUN, [_claim("c1")]))
    sourceless = _claim("c1")
    sourceless.sources = []
    with pytest.raises(UnsourcedClaimError):
        run(store.update_claim(sourceless))


def test_update_replaces_stored_claim():
    """A valid update replaces the stored claim in place (status/confidence change)."""
    store = InMemoryLedgerStore()
    run(store.add_claims(RUN, [_claim("c1")]))
    updated = _claim("c1", text="fact")
    updated.status = ClaimStatus.VERIFIED
    updated.confidence = 0.75
    run(store.update_claim(updated))
    (stored,) = run(store.get_claims(RUN))
    assert stored.status is ClaimStatus.VERIFIED
    assert stored.confidence == 0.75


# --- Fetch recording: idempotency + retrieval --------------------------------

def test_record_and_get_fetch_returns_record():
    """get_fetch returns the FetchRecord that record_fetch persisted."""
    store = InMemoryLedgerStore()
    run(store.record_fetch(RUN, "https://a.example", True, "hash-1"))
    rec = run(store.get_fetch(RUN, "https://a.example"))
    assert rec == FetchRecord(RUN, "https://a.example", True, "hash-1")


def test_get_fetch_unknown_is_none():
    """An un-recorded (run, url) yields None, not a KeyError."""
    store = InMemoryLedgerStore()
    assert run(store.get_fetch(RUN, "https://missing.example")) is None


def test_record_fetch_is_idempotent_per_run_and_url():
    """A later record for the same (run_id, url) OVERWRITES the earlier one."""
    store = InMemoryLedgerStore()
    run(store.record_fetch(RUN, "https://a.example", False, None))
    run(store.record_fetch(RUN, "https://a.example", True, "hash-final"))
    rec = run(store.get_fetch(RUN, "https://a.example"))
    assert rec == FetchRecord(RUN, "https://a.example", True, "hash-final")


def test_record_fetch_is_keyed_by_run_id():
    """The same url under a different run_id is a distinct record."""
    store = InMemoryLedgerStore()
    run(store.record_fetch("run-a", "https://a.example", True, "ha"))
    run(store.record_fetch("run-b", "https://a.example", False, None))
    assert run(store.get_fetch("run-a", "https://a.example")).ok is True
    assert run(store.get_fetch("run-b", "https://a.example")).ok is False


# --- Independence rule (mirror of v_non_independent_verifications) ------------

def test_non_independent_verification_detected():
    """A skeptic source reusing a scholar source is flagged as (claim_id, url)."""
    store = InMemoryLedgerStore()
    reused = "https://shared.example"
    claim = Claim(
        id="c1",
        text="fact",
        sources=[_src(reused)],
        verification=[_src(reused)],  # NOT independent: same url as the scholar source
        produced_by="scholar",
    )
    run(store.add_claims(RUN, [claim]))
    assert store.non_independent_verifications(RUN) == [("c1", reused)]


def test_independent_verification_yields_empty():
    """A skeptic using a genuinely NEW url produces no violations."""
    store = InMemoryLedgerStore()
    claim = Claim(
        id="c1",
        text="fact",
        sources=[_src("https://scholar.example")],
        verification=[_src("https://independent.example")],
        produced_by="scholar",
    )
    run(store.add_claims(RUN, [claim]))
    assert store.non_independent_verifications(RUN) == []


def test_non_independent_verification_empty_when_no_verification():
    """No verification at all -> no independence violation."""
    store = InMemoryLedgerStore()
    run(store.add_claims(RUN, [_claim("c1")]))
    assert store.non_independent_verifications(RUN) == []


# --- snapshot deep-copy isolation --------------------------------------------

def test_snapshot_is_deep_copy_independent_of_later_mutation():
    """snapshot returns deep copies: mutating the stored claim later leaves it intact."""
    store = InMemoryLedgerStore()
    run(store.add_claims(RUN, [_claim("c1")]))
    snap = store.snapshot(RUN)

    # Mutate the LIVE stored claim through a valid update.
    mutated = _claim("c1")
    mutated.status = ClaimStatus.REFUTED
    mutated.sources.append(_src("https://added.example"))
    run(store.update_claim(mutated))

    # The earlier snapshot must be untouched by the later mutation.
    assert snap[0].status is ClaimStatus.UNVERIFIED
    assert len(snap[0].sources) == 1


def test_snapshot_mutation_does_not_corrupt_store():
    """Mutating a snapshot must not reach back into the live store (deep copy)."""
    store = InMemoryLedgerStore()
    run(store.add_claims(RUN, [_claim("c1")]))
    snap = store.snapshot(RUN)
    snap[0].sources.clear()  # vandalize the copy
    (live,) = run(store.get_claims(RUN))
    assert len(live.sources) == 1  # live claim unaffected
