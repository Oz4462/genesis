"""GENESIS ledger — PostgreSQL adapter (third layer of provenance enforcement).

This adapter implements the same ``LedgerStore`` contract as the InMemory store,
but against the schema in ``sql/001_ledger.sql``. It is deliberately isolated in
its own module so the database driver (``asyncpg``) never leaks into the
framework-free core (CLAUDE.md §6). The rest of the system depends on the
``LedgerStore`` Protocol, not on this class.

The driver is imported lazily inside :meth:`connect`, so importing this module
(and therefore the package) never requires ``asyncpg`` to be installed — tests
run on the InMemory store. Instantiating and connecting is what pulls the driver.

Provenance enforcement here is the THIRD layer: the SQL trigger
``claim_requires_source`` rejects a claim with no source rows even if both the
constructor guard and the InMemory check were somehow bypassed.
"""

from __future__ import annotations

from typing import Sequence

from ..core.errors import GenesisError, UnsourcedClaimError
from ..core.state import (
    Claim,
    ClaimStatus,
    SourceRef,
    SourceSupport,
)
from .store import UnknownClaimError


def _support_to_db(support: SourceSupport | None) -> str:
    """Map a SourceRef.support to the DB enum.

    A scholar source backs the claim by definition (scholar only extracts a
    Claim *from* a supporting source), so a missing direction defaults to
    'supports'. A contradicting source must be set explicitly (skeptic does
    this when it finds a refutation) — we never silently invent a contradiction.
    """
    if support is SourceSupport.CONTRADICTS:
        return "contradicts"
    return "supports"


def _support_from_db(value: str) -> SourceSupport:
    return (
        SourceSupport.CONTRADICTS
        if value == "contradicts"
        else SourceSupport.SUPPORTS
    )


class PostgresLedgerStore:
    """Durable ledger backed by PostgreSQL. Satisfies the ``LedgerStore`` Protocol.

    Usage::

        store = PostgresLedgerStore(dsn)
        await store.connect()
        await store.ensure_run(run_id, question, config_hash)
        await store.add_claims(run_id, claims)
        ...
        await store.close()

    Not exercised by the in-sandbox test-suite (no database there); its
    correctness rests on matching ``sql/001_ledger.sql`` exactly. The InMemory
    store is the behavioural reference and enforces the identical invariants.
    """

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool = None  # asyncpg.Pool, created in connect()

    async def connect(self) -> None:
        """Open the connection pool. Imports asyncpg lazily (optional dep)."""
        try:
            import asyncpg  # noqa: PLC0415 — intentional lazy/optional import
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise GenesisError(
                "PostgresLedgerStore requires 'asyncpg'. Install it, or use "
                "InMemoryLedgerStore for tests/local runs."
            ) from exc
        self._pool = await asyncpg.create_pool(self._dsn)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def _require_pool(self):
        if self._pool is None:
            raise GenesisError("PostgresLedgerStore.connect() was not called.")
        return self._pool

    async def ensure_run(self, run_id: str, question: str, config_hash: str) -> None:
        """Create the run row (FK target for claims/fetches) if absent.

        Must be called before :meth:`add_claims` — the ``claims.run_id`` foreign
        key requires it. ``config_hash`` ties the run to its exact configuration
        for reproducibility (acceptance criterion A5).
        """
        pool = self._require_pool()
        await pool.execute(
            """
            INSERT INTO runs (run_id, question, config_hash)
            VALUES ($1, $2, $3)
            ON CONFLICT (run_id) DO NOTHING
            """,
            run_id,
            question,
            config_hash,
        )

    async def add_claims(self, run_id: str, claims: Sequence[Claim]) -> None:
        """Insert new claims and their scholar sources in one transaction.

        The DEFERRABLE ``claim_requires_source`` trigger checks at COMMIT that
        every claim has >= 1 source row, so claim + sources insert together.

        Raises:
            UnsourcedClaimError: a claim has empty ``sources`` (caught before the
                DB so the message names the offending claim).
        """
        for claim in claims:
            if not claim.sources:
                raise UnsourcedClaimError(claim.id, claim.text)

        pool = self._require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                for claim in claims:
                    await conn.execute(
                        """
                        INSERT INTO claims
                          (id, run_id, text, quote, status, confidence,
                           produced_by, model)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                        """,
                        claim.id,
                        run_id,
                        claim.text,
                        claim.quote,
                        claim.status.value,
                        claim.confidence,
                        claim.produced_by,
                        claim.model,
                    )
                    for ref in claim.sources:
                        await conn.execute(
                            """
                            INSERT INTO claim_sources
                              (claim_id, url_or_id, support, origin, span)
                            VALUES ($1,$2,$3,'scholar',$4)
                            ON CONFLICT (claim_id, url_or_id, origin) DO NOTHING
                            """,
                            claim.id,
                            ref.url_or_id,
                            _support_to_db(ref.support),
                            ref.span,
                        )

    async def update_claim(self, claim: Claim) -> None:
        """Update status/confidence and append skeptic verification sources.

        Raises:
            UnknownClaimError: the claim id does not exist (loud, not silent).
            UnsourcedClaimError: the update would leave the claim sourceless.
        """
        if not claim.sources:
            raise UnsourcedClaimError(claim.id, claim.text)

        pool = self._require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                status = await conn.execute(
                    """
                    UPDATE claims
                       SET status = $2, confidence = $3, model = $4
                     WHERE id = $1
                    """,
                    claim.id,
                    claim.status.value,
                    claim.confidence,
                    claim.model,
                )
                # asyncpg returns e.g. 'UPDATE 1'; 0 rows means unknown claim.
                if status.endswith(" 0"):
                    raise UnknownClaimError(claim.id)
                for ref in claim.verification:
                    await conn.execute(
                        """
                        INSERT INTO claim_sources
                          (claim_id, url_or_id, support, origin, span)
                        VALUES ($1,$2,$3,'skeptic',$4)
                        ON CONFLICT (claim_id, url_or_id, origin) DO NOTHING
                        """,
                        claim.id,
                        ref.url_or_id,
                        _support_to_db(ref.support),
                        ref.span,
                    )

    async def get_claims(self, run_id: str) -> list[Claim]:
        """Reconstruct claims (with scholar sources + skeptic verifications).

        Ordered by ``created_at, id`` for deterministic output (A5).
        """
        pool = self._require_pool()
        rows = await pool.fetch(
            """
            SELECT id, text, quote, status, confidence, produced_by, model,
                   created_at
              FROM claims
             WHERE run_id = $1
             ORDER BY created_at, id
            """,
            run_id,
        )
        claims: list[Claim] = []
        for r in rows:
            src_rows = await pool.fetch(
                """
                SELECT url_or_id, support, origin, span
                  FROM claim_sources
                 WHERE claim_id = $1
                 ORDER BY origin, url_or_id
                """,
                r["id"],
            )
            sources: list[SourceRef] = []
            verification: list[SourceRef] = []
            for s in src_rows:
                ref = SourceRef(
                    url_or_id=s["url_or_id"],
                    retrieved=True,  # presence in claim_sources implies a fetch
                    span=s["span"],
                    support=_support_from_db(s["support"]),
                )
                (verification if s["origin"] == "skeptic" else sources).append(ref)
            claims.append(
                Claim(
                    id=r["id"],
                    text=r["text"],
                    sources=sources,
                    quote=r["quote"],
                    status=ClaimStatus(r["status"]),
                    confidence=r["confidence"],
                    verification=verification,
                    produced_by=r["produced_by"],
                    model=r["model"],
                    created_at=r["created_at"],
                )
            )
        return claims

    async def record_fetch(
        self, run_id: str, url: str, ok: bool, content_hash: str | None
    ) -> None:
        """Upsert a fetch outcome (PK run_id+url_or_id)."""
        pool = self._require_pool()
        await pool.execute(
            """
            INSERT INTO fetches (run_id, url_or_id, ok, content_hash)
            VALUES ($1,$2,$3,$4)
            ON CONFLICT (run_id, url_or_id)
            DO UPDATE SET ok = EXCLUDED.ok,
                          content_hash = EXCLUDED.content_hash,
                          fetched_at = now()
            """,
            run_id,
            url,
            ok,
            content_hash,
        )

    async def non_independent_verifications(
        self, run_id: str
    ) -> list[tuple[str, str]]:
        """Query the independence-violation view, scoped to one run."""
        pool = self._require_pool()
        rows = await pool.fetch(
            """
            SELECT v.claim_id, v.url_or_id
              FROM v_non_independent_verifications v
              JOIN claims c ON c.id = v.claim_id
             WHERE c.run_id = $1
            """,
            run_id,
        )
        return [(r["claim_id"], r["url_or_id"]) for r in rows]
