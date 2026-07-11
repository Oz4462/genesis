"""GENESIS ledger — the canonical, dependency-free InMemory store.

The ledger is where the anti-hallucination guarantee becomes *persistent*: every
factual Claim lives here together with its provenance, its verification status,
and the record of which sources were actually retrieved.

This module provides ``InMemoryLedgerStore``. It enforces the mandatory-provenance
rule as the SECOND of three layers:

  1. ``Claim.__post_init__``           — a sourceless Claim cannot be constructed.
  2. ``InMemoryLedgerStore.add_claims`` — re-checked here (sources is mutable).
  3. ``sql/001_ledger.sql`` trigger     — enforced again at the database layer.

Belt, suspenders, and a backup belt (CLAUDE.md §1). The PostgreSQL adapter lives
in ``ledger/postgres.py`` so that no database driver leaks into the
framework-free core (CLAUDE.md §6).
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Sequence

from ..core.errors import GenesisError, UnsourcedClaimError
from ..core.state import Claim


@dataclass(frozen=True)
class FetchRecord:
    """Audit record: did we actually retrieve this source in this run?

    The gate (PHASE_ALPHA §4 condition 5) rejects citations whose fetch was not
    ``ok``. Recording every attempt — success and failure — is what makes a
    "dead citation" detectable instead of silently trusted.
    """

    run_id: str
    url_or_id: str
    ok: bool
    content_hash: str | None = None


class UnknownClaimError(GenesisError):
    """``update_claim`` was called for a claim id the ledger has never seen.

    Loud failure instead of silently inserting: an update to a non-existent
    claim almost always means a wiring bug upstream, and swallowing it would let
    state drift unnoticed.
    """

    def __init__(self, claim_id: str) -> None:
        super().__init__(
            f"Cannot update unknown claim {claim_id!r}: it was never added to the ledger."
        )


class InMemoryLedgerStore:
    """Process-local ledger. Satisfies the ``LedgerStore`` Protocol.

    Used for tests and for runs that do not need durable persistence. Enforces
    the same invariants as the Postgres schema:

      * no claim without >= 1 source (mandatory provenance);
      * fetch outcomes are recorded and queryable (dead-citation detection);
      * non-independent skeptic verifications are detectable (independence rule,
        PHASE_ALPHA §3.4 — mirrors the SQL view ``v_non_independent_verifications``).

    Determinism: :meth:`get_claims` returns claims in insertion order, so the
    same sequence of operations yields an identical snapshot. This is part of
    what makes a run reproducible (acceptance criterion A5).
    """

    def __init__(self) -> None:
        # run_id -> list of claim ids in insertion order (determinism / A5)
        self._order: dict[str, list[str]] = {}
        # claim id -> Claim (claim ids are globally unique by construction)
        self._claims: dict[str, Claim] = {}
        # (run_id, url_or_id) -> FetchRecord
        self._fetches: dict[tuple[str, str], FetchRecord] = {}

    # --- LedgerStore protocol -------------------------------------------------

    async def add_claims(self, run_id: str, claims: Sequence[Claim]) -> None:
        """Persist new claims. Rejects any claim without a source (layer 2).

        The whole batch is validated *before* any mutation, so a single bad
        claim never leaves the ledger in a half-written state.

        Raises:
            UnsourcedClaimError: a claim has empty ``sources``. Re-checked here
                even though the constructor guards it, because ``sources`` is a
                mutable list and could have been emptied after construction.
            ValueError: a claim id already exists. The ledger is append-only for
                creation; mutations go through :meth:`update_claim`.
        """
        for claim in claims:
            self._assert_claim_integrity(claim)
            if claim.id in self._claims:
                raise ValueError(
                    f"Claim {claim.id!r} already in ledger; "
                    "use update_claim for changes."
                )
        for claim in claims:
            self._claims[claim.id] = claim
            self._order.setdefault(run_id, []).append(claim.id)

    async def update_claim(self, claim: Claim) -> None:
        """Persist a status/confidence/verification update for an existing claim.

        Raises:
            UnknownClaimError: the claim was never added (loud, not silent).
            UnsourcedClaimError: the update would leave the claim sourceless.
            ValueError: non-finite or out-of-range confidence after mutation.
        """
        if claim.id not in self._claims:
            raise UnknownClaimError(claim.id)
        self._assert_claim_integrity(claim)
        self._claims[claim.id] = claim

    @staticmethod
    def _assert_claim_integrity(claim: Claim) -> None:
        """Layer-2 provenance + confidence backstop (mutable Claim fields).

        Re-checks constructor invariants because ``sources`` is a mutable list
        and ``confidence`` can be reassigned after construction (Claim is not
        frozen). The gate is the third line of defense; the ledger refuses to
        persist poison (REWORK 2026-07-11).
        """
        if not claim.sources:
            raise UnsourcedClaimError(claim.id, claim.text)
        for ref in claim.sources:
            if not str(ref.url_or_id).strip():
                raise ValueError(
                    f"Claim {claim.id!r}: source url_or_id must be non-empty"
                )
        conf = claim.confidence
        if (
            isinstance(conf, bool)
            or not isinstance(conf, (int, float))
            or not math.isfinite(conf)
            or not (0.0 <= float(conf) <= 1.0)
        ):
            raise ValueError(
                f"Claim {claim.id!r}: confidence must be finite in [0, 1], "
                f"got {conf!r}"
            )

    async def get_claims(self, run_id: str) -> list[Claim]:
        """Return all claims for a run, in deterministic insertion order."""
        return [self._claims[cid] for cid in self._order.get(run_id, [])]

    async def record_fetch(
        self, run_id: str, url: str, ok: bool, content_hash: str | None
    ) -> None:
        """Record that a source was (or was not) successfully retrieved.

        Idempotent per ``(run_id, url)``: a later attempt overwrites the earlier
        record, matching the Postgres primary key ``(run_id, url_or_id)``.
        """
        self._fetches[(run_id, url)] = FetchRecord(run_id, url, ok, content_hash)

    # --- Extra queries (mirror SQL helpers; not part of the protocol) ---------

    async def get_fetch(self, run_id: str, url: str) -> FetchRecord | None:
        """Return the recorded fetch outcome for a source, or ``None``."""
        return self._fetches.get((run_id, url))

    def non_independent_verifications(self, run_id: str) -> list[tuple[str, str]]:
        """Mirror of ``v_non_independent_verifications`` (PHASE_ALPHA §3.4).

        Returns ``(claim_id, url)`` pairs where a skeptic verification source
        reuses a scholar source for the SAME claim — a violation of the
        independence rule. A correct ``skeptic`` yields an empty list here.
        """
        violations: list[tuple[str, str]] = []
        for cid in self._order.get(run_id, []):
            claim = self._claims[cid]
            scholar_urls = {s.url_or_id for s in claim.sources}
            for v in claim.verification:
                if v.url_or_id in scholar_urls:
                    violations.append((claim.id, v.url_or_id))
        return violations

    def snapshot(self, run_id: str) -> list[Claim]:
        """Deep copy of a run's claims, for reproducibility comparisons (A5).

        A snapshot is independent of later mutations, so two runs can be diffed
        claim-by-claim to prove determinism.
        """
        return [
            copy.deepcopy(self._claims[cid])
            for cid in self._order.get(run_id, [])
        ]
