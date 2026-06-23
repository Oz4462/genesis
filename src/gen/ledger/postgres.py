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

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from ..core.errors import GenesisError, UnsourcedClaimError
from ..core.state import (
    Claim,
    ClaimStatus,
    SourceRef,
    SourceSupport,
)
from .store import UnknownClaimError

#: Directory holding the SQL schema files (sql/001_ledger.sql, sql/002_embeddings.sql).
#: postgres.py is src/gen/ledger/postgres.py; the repo root is three parents up.
_SQL_DIR = Path(__file__).resolve().parents[3] / "sql"

#: An embedder: text -> a sequence of floats (a dense vector). Injected, never
#: constructed here, so the ledger never silently hard-depends on Ollama / a model
#: server. ``tools.ollama_embedder.OllamaEmbedder`` and the test embedder both satisfy
#: it. The vector's length MUST equal the schema dimension (pgvector rejects a
#: mismatch — loud, not silent).
Embedder = Callable[[str], Sequence[float]]


@dataclass(frozen=True)
class PostgresConfig:
    """Connection + embedding configuration for :class:`PostgresLedgerStore`.

    Resolved from environment variables with sane local defaults (CLAUDE.md: no
    silent defaults for *facts*, but a connection target is infrastructure, not a
    fact — and every default here is overridable and reported). The defaults target
    a local PostgreSQL reachable by **peer auth** over the unix socket as the OS
    user, which is how the GENESIS dev box is set up (role ``genesis`` == OS user).

    Environment variables (all optional):
      * ``GENESIS_DB_DSN``    — full asyncpg/libpq DSN; if set it WINS over the parts.
      * ``GENESIS_DB_HOST``   — host or socket dir (default: the unix socket dir).
      * ``GENESIS_DB_PORT``   — TCP port (default 5432; ignored for a socket path).
      * ``GENESIS_DB_NAME``   — database name (default ``genesis``).
      * ``GENESIS_DB_USER``   — role (default: ``$USER`` / ``genesis``).
      * ``GENESIS_DB_PASSWORD`` — password (default: none → peer auth).
      * ``GENESIS_EMBED_DIM`` — embedding dimension for the pgvector column
        (default 768, the embeddinggemma size). MUST match the injected embedder.
    """

    dsn: str | None
    host: str
    port: int
    database: str
    user: str
    password: str | None
    embed_dim: int

    @staticmethod
    def from_env() -> "PostgresConfig":
        """Build the config from ``GENESIS_DB_*`` env vars with local-peer defaults."""
        default_user = os.environ.get("USER") or "genesis"
        return PostgresConfig(
            dsn=os.environ.get("GENESIS_DB_DSN"),
            host=os.environ.get("GENESIS_DB_HOST", "/var/run/postgresql"),
            port=int(os.environ.get("GENESIS_DB_PORT", "5432")),
            database=os.environ.get("GENESIS_DB_NAME", "genesis"),
            user=os.environ.get("GENESIS_DB_USER", default_user),
            password=os.environ.get("GENESIS_DB_PASSWORD") or None,
            embed_dim=int(os.environ.get("GENESIS_EMBED_DIM", "768")),
        )

    def connect_kwargs(self) -> dict:
        """asyncpg ``create_pool`` kwargs. A full ``dsn`` overrides the parts."""
        if self.dsn:
            return {"dsn": self.dsn}
        kwargs: dict = {
            "host": self.host,
            "database": self.database,
            "user": self.user,
        }
        # A unix-socket host needs no port; a TCP host does. asyncpg treats a host
        # starting with '/' as a socket directory.
        if not self.host.startswith("/"):
            kwargs["port"] = self.port
        if self.password is not None:
            kwargs["password"] = self.password
        return kwargs


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

    def __init__(self, dsn: str | None = None, *, config: PostgresConfig | None = None) -> None:
        """Configure the store. Pass a libpq ``dsn`` string OR a :class:`PostgresConfig`.

        Backward-compatible: ``PostgresLedgerStore(dsn)`` still works. With neither
        argument the config is read from ``GENESIS_DB_*`` env vars (local-peer
        defaults). The connection is NOT opened until :meth:`connect`.
        """
        if config is not None:
            self._config = config
        elif dsn is not None:
            self._config = PostgresConfig.from_env()
            # an explicit dsn argument overrides whatever from_env() picked up
            object.__setattr__(self._config, "dsn", dsn)
        else:
            self._config = PostgresConfig.from_env()
        self._pool = None  # asyncpg.Pool, created in connect()

    @classmethod
    def from_env(cls) -> "PostgresLedgerStore":
        """Construct from ``GENESIS_DB_*`` env vars (the standard local entrypoint)."""
        return cls(config=PostgresConfig.from_env())

    @property
    def embed_dim(self) -> int:
        """The pgvector column dimension this store expects from injected embedders."""
        return self._config.embed_dim

    async def connect(self) -> None:
        """Open the connection pool. Imports asyncpg lazily (optional dep).

        Raises:
            GenesisError: ``asyncpg`` is not installed, or the server is unreachable
                (the underlying asyncpg error is chained — loud, not a silent None
                pool that fails cryptically later).
        """
        try:
            import asyncpg  # noqa: PLC0415 — intentional lazy/optional import
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise GenesisError(
                "PostgresLedgerStore requires 'asyncpg'. Install it, or use "
                "InMemoryLedgerStore for tests/local runs."
            ) from exc
        try:
            self._pool = await asyncpg.create_pool(**self._config.connect_kwargs())
        except (OSError, asyncpg.PostgresError) as exc:
            raise GenesisError(
                f"PostgresLedgerStore could not connect to PostgreSQL "
                f"({self._config.connect_kwargs()!r}): {exc}"
            ) from exc

    async def ensure_schema(self) -> None:
        """Apply the ledger schema (sql/001) + the pgvector embedding schema (sql/002).

        Idempotent: every statement is ``CREATE … IF NOT EXISTS`` / ``CREATE OR
        REPLACE``. The pgvector column dimension in 002 is substituted from
        ``config.embed_dim`` (pgvector needs a fixed dimension per column). Creating
        the ``vector`` extension needs sufficient privilege; on the GENESIS box the
        ``genesis`` role owns the ``genesis`` database, so it can.

        Raises:
            GenesisError: a schema file is missing, or the DB rejects a statement
                (e.g. the ``vector`` extension is not available — surfaced, not
                swallowed).
        """
        pool = self._require_pool()
        ledger_sql = _SQL_DIR / "001_ledger.sql"
        embed_sql = _SQL_DIR / "002_embeddings.sql"
        for path in (ledger_sql, embed_sql):
            if not path.is_file():
                raise GenesisError(f"schema file missing: {path}")
        try:
            await pool.execute(ledger_sql.read_text(encoding="utf-8"))
            embed_ddl = embed_sql.read_text(encoding="utf-8").replace(
                "{dim}", str(self._config.embed_dim)
            )
            await pool.execute(embed_ddl)
        except Exception as exc:  # noqa: BLE001 - any DDL failure is surfaced loudly
            raise GenesisError(f"PostgresLedgerStore.ensure_schema failed: {exc}") from exc

        # `CREATE TABLE IF NOT EXISTS` does NOT alter an existing table's column type,
        # so if claim_embeddings was created earlier at a DIFFERENT dimension, the
        # vector column silently keeps the old size. Detect that and fail LOUD — a
        # silent dimension mismatch would corrupt every later similarity query.
        existing = await pool.fetchval(
            "SELECT atttypmod FROM pg_attribute "
            "WHERE attrelid = 'claim_embeddings'::regclass AND attname = 'embedding'"
        )
        # pgvector stores the dimension directly in atttypmod (no -4 VARHDRSZ offset).
        if existing is not None and existing not in (-1, self._config.embed_dim):
            raise GenesisError(
                f"claim_embeddings.embedding already exists with dimension {existing}, "
                f"but this store is configured for {self._config.embed_dim}. A vector "
                f"column's dimension is fixed; migrate the table (or set "
                f"GENESIS_EMBED_DIM={existing}) — refusing to run with a mismatch."
            )

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

    # --- pgvector semantic recall over stored claims (sql/002) ----------------

    def _check_dim(self, vector: Sequence[float]) -> list[float]:
        """Validate a vector's length against the schema dimension and return it as
        a plain float list. A mismatch is a loud error (the alternative — letting
        pgvector reject it with an opaque message, or worse, silently comparing
        across embedding spaces — violates the no-silent-defaults rule)."""
        vec = [float(x) for x in vector]
        if len(vec) != self._config.embed_dim:
            raise GenesisError(
                f"embedding dimension {len(vec)} != configured dimension "
                f"{self._config.embed_dim} (set GENESIS_EMBED_DIM to match your "
                f"embedder, or pass the right PostgresConfig)"
            )
        return vec

    @staticmethod
    def _to_pgvector(vec: Sequence[float]) -> str:
        """Render a vector as the pgvector text literal ``[v0,v1,...]`` (the form
        pgvector accepts via a ``::vector`` cast without a registered codec)."""
        return "[" + ",".join(repr(float(x)) for x in vec) + "]"

    async def store_embedding(
        self, claim_id: str, text: str, embedder: Embedder, *, embed_model: str
    ) -> None:
        """Embed ``text`` with the injected ``embedder`` and store the vector for an
        EXISTING claim. Upserts on (claim_id, embed_model).

        ``embed_model`` is recorded so vectors from different embedders are never
        silently compared. The dimension is validated against the schema before the
        write (loud on mismatch).

        Raises:
            GenesisError: dimension mismatch, or the claim does not exist (the FK
                rejects an embedding for an unknown claim — surfaced).
        """
        vec = self._check_dim(embedder(text))
        pool = self._require_pool()
        literal = self._to_pgvector(vec)
        try:
            await pool.execute(
                """
                INSERT INTO claim_embeddings (claim_id, embed_model, dim, embedding)
                VALUES ($1, $2, $3, $4::vector)
                ON CONFLICT (claim_id, embed_model)
                DO UPDATE SET embedding = EXCLUDED.embedding,
                              dim = EXCLUDED.dim,
                              created_at = now()
                """,
                claim_id,
                embed_model,
                len(vec),
                literal,
            )
        except Exception as exc:  # noqa: BLE001 - FK / cast failures surfaced loudly
            raise GenesisError(
                f"store_embedding failed for claim {claim_id!r}: {exc}"
            ) from exc

    async def recall_similar(
        self,
        query: str,
        embedder: Embedder,
        *,
        embed_model: str,
        limit: int = 5,
        run_id: str | None = None,
    ) -> list[tuple[Claim, float]]:
        """Recall the claims whose stored embedding is most similar to ``query``.

        Embeds the query with the SAME injected embedder, then ranks by pgvector
        cosine distance (``<=>``) over vectors produced by the SAME ``embed_model``
        (cross-model vectors are excluded — no apples-to-oranges similarity). Returns
        ``(Claim, cosine_similarity)`` pairs, most-similar first; similarity is
        ``1 - distance`` in ``[-1, 1]`` (higher = closer). Optionally scoped to one
        ``run_id``.

        This is the retrieval half of "no claim without source": before asserting
        something new, ask whether a stored, provenance-backed claim already covers
        it. The Claims returned carry their full provenance (sources + verification),
        reconstructed exactly as :meth:`get_claims` does.

        Raises:
            GenesisError: dimension mismatch on the query embedding.
        """
        vec = self._check_dim(embedder(query))
        pool = self._require_pool()
        literal = self._to_pgvector(vec)
        params: list = [embed_model, literal]
        run_clause = ""
        if run_id is not None:
            params.append(run_id)
            run_clause = f"AND c.run_id = ${len(params)}"
        params.append(limit)
        rows = await pool.fetch(
            f"""
            SELECT c.id, c.text, c.quote, c.status, c.confidence, c.produced_by,
                   c.model, c.created_at,
                   1 - (e.embedding <=> $2::vector) AS similarity
              FROM claim_embeddings e
              JOIN claims c ON c.id = e.claim_id
             WHERE e.embed_model = $1 {run_clause}
             ORDER BY e.embedding <=> $2::vector
             LIMIT ${len(params)}
            """,
            *params,
        )
        out: list[tuple[Claim, float]] = []
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
                    retrieved=True,
                    span=s["span"],
                    support=_support_from_db(s["support"]),
                )
                (verification if s["origin"] == "skeptic" else sources).append(ref)
            claim = Claim(
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
            out.append((claim, float(r["similarity"])))
        return out
