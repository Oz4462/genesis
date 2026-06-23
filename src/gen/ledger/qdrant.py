"""GENESIS ledger — Qdrant adapter (an alternative vector store behind the SAME seam).

The PostgreSQL adapter (``ledger/postgres.py``) recalls provenance-backed Claims by
pgvector cosine similarity over vectors produced by an INJECTED embedder. This module
offers the same semantic-recall capability against a Qdrant vector database instead of
pgvector — same injected-``Embedder`` seam, same method names, same return shape
``list[(Claim, similarity)]`` — so a caller can swap the backend without changing how it
recalls facts.

Why a second backend: Qdrant is a purpose-built vector engine (HNSW, payload filtering,
no SQL/pgvector extension required). It is the natural choice when the deployment has a
Qdrant server but no PostgreSQL+pgvector, and it keeps the recall path honest about the
ONE thing that must never drift: vectors from different embedders are never compared
(the ``embed_model`` is stored on every point and every query filters on it).

Design mirrors the Postgres adapter exactly:
  * The embedder is INJECTED (``Embedder = Callable[[str], Sequence[float]]``), never
    constructed here — the ledger never silently hard-depends on a model server.
  * The vector dimension is validated against the configured dimension before any write
    or query (loud on mismatch — never a silent cross-space comparison).
  * The full Claim (with sources + verification provenance) is stored in the point
    payload and reconstructed on recall, exactly as ``get_claims`` would return it.

The ``qdrant-client`` import is LAZY (inside :meth:`connect`), so importing this module
never requires the client to be installed — the InMemory store remains the dependency-free
default. Failure is LOUD and typed (``GenesisError``): a missing client, an unreachable
server, or a dimension mismatch is surfaced, never swallowed into a guessed value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Sequence

from ..core.errors import GenesisError
from ..core.state import (
    Claim,
    ClaimStatus,
    SourceRef,
    SourceSupport,
)

#: text -> dense vector. Identical seam to ledger.postgres.Embedder (injected, never
#: built here; its length MUST equal the configured dimension).
Embedder = Callable[[str], Sequence[float]]


def qdrant_available() -> bool:
    """True iff the optional ``qdrant_client`` package can be imported.

    Mirrors ``cad_available`` / ``openfoam_available``: a False is a definitive
    'no client', so server-dependent tests can skip-guard cleanly. It does NOT
    prove a server is reachable — the first real call does that, loudly.
    """
    try:
        import qdrant_client  # noqa: F401
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class QdrantConfig:
    """Connection + embedding configuration for :class:`QdrantLedgerStore`.

    Resolved from environment variables with local defaults (a connection target is
    infrastructure, not a fact — every default is overridable and reported here).

    Environment variables (all optional):
      * ``GENESIS_QDRANT_URL``        — full URL (e.g. ``http://localhost:6333``); WINS
        over host/port if set.
      * ``GENESIS_QDRANT_HOST``       — host (default ``localhost``).
      * ``GENESIS_QDRANT_PORT``       — REST port (default 6333).
      * ``GENESIS_QDRANT_COLLECTION`` — collection name (default ``genesis_claims``).
      * ``GENESIS_EMBED_DIM``         — vector dimension (default 768, the
        embeddinggemma size). MUST match the injected embedder.
    """

    url: str | None
    host: str
    port: int
    collection: str
    embed_dim: int

    @staticmethod
    def from_env() -> "QdrantConfig":
        """Build the config from ``GENESIS_QDRANT_*`` env vars with local defaults."""
        return QdrantConfig(
            url=os.environ.get("GENESIS_QDRANT_URL"),
            host=os.environ.get("GENESIS_QDRANT_HOST", "localhost"),
            port=int(os.environ.get("GENESIS_QDRANT_PORT", "6333")),
            collection=os.environ.get("GENESIS_QDRANT_COLLECTION", "genesis_claims"),
            embed_dim=int(os.environ.get("GENESIS_EMBED_DIM", "768")),
        )


def _source_to_payload(ref: SourceRef) -> dict:
    """Serialise a SourceRef to a JSON-safe payload dict (Qdrant stores JSON)."""
    return {
        "url_or_id": ref.url_or_id,
        "retrieved": ref.retrieved,
        "content_hash": ref.content_hash,
        "span": ref.span,
        "support": (ref.support.value if ref.support is not None else "supports"),
    }


def _source_from_payload(d: dict) -> SourceRef:
    """Reconstruct a SourceRef from its payload dict."""
    support = (
        SourceSupport.CONTRADICTS
        if d.get("support") == "contradicts"
        else SourceSupport.SUPPORTS
    )
    return SourceRef(
        url_or_id=d["url_or_id"],
        retrieved=bool(d.get("retrieved", True)),
        content_hash=d.get("content_hash"),
        span=d.get("span"),
        support=support,
    )


def _point_id(claim_id: str, embed_model: str) -> str:
    """A deterministic UUID5 point id from (claim_id, embed_model).

    Qdrant point ids must be an unsigned int or a UUID; GENESIS claim ids are
    arbitrary strings. UUID5 makes the mapping deterministic and collision-free
    per (claim, model), so re-storing the same claim+model upserts the same point
    (idempotent, mirroring the Postgres ``ON CONFLICT (claim_id, embed_model)``).
    """
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"genesis:{embed_model}:{claim_id}"))


class QdrantLedgerStore:
    """Semantic recall of provenance-backed Claims, backed by Qdrant.

    This is NOT a full ``LedgerStore`` (it does not enforce the add/update lifecycle —
    that stays in the InMemory/Postgres stores). It provides the *recall* half: store a
    claim's embedding, then recall the claims most similar to a query — the retrieval
    side of "before asserting something new, ask whether a stored, provenance-backed
    claim already covers it".

    Determinism: cosine distance over a fixed HNSW graph; per-(claim, model) point ids
    make re-stores idempotent. Cross-model safety: every point records its ``embed_model``
    and every query filters on it, so vectors from different embedders are never compared.
    """

    def __init__(
        self, url: str | None = None, *, config: QdrantConfig | None = None
    ) -> None:
        self._config = config or QdrantConfig.from_env()
        if url is not None:
            # QdrantConfig is frozen; honour an explicit url by rebuilding the config.
            self._config = QdrantConfig(
                url=url,
                host=self._config.host,
                port=self._config.port,
                collection=self._config.collection,
                embed_dim=self._config.embed_dim,
            )
        self._client = None  # type: ignore[assignment]

    @property
    def embed_dim(self) -> int:
        """The vector dimension this store expects from injected embedders."""
        return self._config.embed_dim

    @property
    def collection(self) -> str:
        """The Qdrant collection this store reads/writes."""
        return self._config.collection

    # --- lifecycle ------------------------------------------------------------

    def connect(self) -> None:
        """Open the Qdrant client (lazy import of ``qdrant_client``).

        Raises:
            GenesisError: the ``qdrant_client`` package is not installed (loud, with
                the install hint) — never a silent no-op.
        """
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:  # pragma: no cover - exercised only without the client
            raise GenesisError(
                "the Qdrant ledger backend needs the optional 'qdrant-client' package; "
                "install it with `pip install qdrant-client`, or use the InMemory / "
                "Postgres ledger store."
            ) from exc
        if self._config.url:
            self._client = QdrantClient(url=self._config.url)
        else:
            self._client = QdrantClient(host=self._config.host, port=self._config.port)

    def close(self) -> None:
        """Close the underlying client (if open)."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "QdrantLedgerStore":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _require_client(self):
        if self._client is None:
            raise GenesisError(
                "QdrantLedgerStore is not connected; call connect() (or use it as a "
                "context manager) before storing or recalling."
            )
        return self._client

    def ensure_collection(self) -> None:
        """Create the collection (cosine distance, configured dimension) if absent.

        Idempotent: an existing collection is left as-is, UNLESS its vector size does
        not match the configured dimension — that is a loud error (a silent dimension
        mismatch would corrupt every later similarity query, exactly the failure the
        Postgres adapter guards against).
        """
        from qdrant_client import models

        client = self._require_client()
        existing = {c.name for c in client.get_collections().collections}
        if self._config.collection in existing:
            info = client.get_collection(self._config.collection)
            size = info.config.params.vectors.size  # type: ignore[union-attr]
            if size != self._config.embed_dim:
                raise GenesisError(
                    f"Qdrant collection {self._config.collection!r} already exists with "
                    f"vector size {size}, but this store is configured for "
                    f"{self._config.embed_dim} (set GENESIS_EMBED_DIM to match your "
                    f"embedder, or use a different collection)."
                )
            return
        client.create_collection(
            collection_name=self._config.collection,
            vectors_config=models.VectorParams(
                size=self._config.embed_dim, distance=models.Distance.COSINE
            ),
        )

    # --- store / recall (mirror PostgresLedgerStore) --------------------------

    def _check_dim(self, vector: Sequence[float]) -> list[float]:
        """Validate a vector's length against the configured dimension (loud on
        mismatch — never a silent cross-space comparison)."""
        vec = [float(x) for x in vector]
        if len(vec) != self._config.embed_dim:
            raise GenesisError(
                f"embedding dimension {len(vec)} != configured dimension "
                f"{self._config.embed_dim} (set GENESIS_EMBED_DIM to match your "
                f"embedder, or pass the right QdrantConfig)"
            )
        return vec

    def store_embedding(
        self, claim: Claim, embedder: Embedder, *, embed_model: str
    ) -> None:
        """Embed ``claim.text`` with the injected embedder and upsert the vector.

        Unlike the Postgres adapter (which keeps the Claim in a relational table and
        only stores the vector), Qdrant has no separate claims table, so the full Claim
        — including its sources and verification provenance — is stored in the point
        payload and reconstructed verbatim on recall. The point id is deterministic per
        (claim, model), so a re-store upserts (idempotent).

        ``embed_model`` is recorded on the point so vectors from different embedders are
        never silently compared. The dimension is validated before the write.

        Raises:
            GenesisError: dimension mismatch, or not connected.
            UnsourcedClaimError: the claim has no sources (re-checked — a sourceless
                fact must never be persisted, CLAUDE.md §1).
        """
        if not claim.sources:
            from ..core.errors import UnsourcedClaimError

            raise UnsourcedClaimError(claim.id, claim.text)
        from qdrant_client import models

        vec = self._check_dim(embedder(claim.text))
        client = self._require_client()
        payload = {
            "claim_id": claim.id,
            "embed_model": embed_model,
            "text": claim.text,
            "quote": claim.quote,
            "status": claim.status.value,
            "confidence": claim.confidence,
            "produced_by": claim.produced_by,
            "model": claim.model,
            "created_at": claim.created_at.isoformat(),
            "sources": [_source_to_payload(s) for s in claim.sources],
            "verification": [_source_to_payload(s) for s in claim.verification],
        }
        try:
            client.upsert(
                collection_name=self._config.collection,
                points=[
                    models.PointStruct(
                        id=_point_id(claim.id, embed_model),
                        vector=vec,
                        payload=payload,
                    )
                ],
            )
        except Exception as exc:  # noqa: BLE001 - surfaced loudly
            raise GenesisError(
                f"Qdrant store_embedding failed for claim {claim.id!r}: {exc}"
            ) from exc

    def recall_similar(
        self,
        query: str,
        embedder: Embedder,
        *,
        embed_model: str,
        limit: int = 5,
    ) -> list[tuple[Claim, float]]:
        """Recall the claims whose stored embedding is most similar to ``query``.

        Embeds the query with the SAME injected embedder, then ranks by Qdrant cosine
        similarity over vectors produced by the SAME ``embed_model`` (filtered — no
        apples-to-oranges similarity). Returns ``(Claim, cosine_similarity)`` pairs,
        most-similar first; the Claims carry their full provenance, reconstructed from
        the point payload exactly as :meth:`PostgresLedgerStore.recall_similar` does.
        Cosine similarity is in ``[-1, 1]`` (higher = closer).

        Raises:
            GenesisError: dimension mismatch on the query embedding, or not connected.
        """
        from qdrant_client import models

        vec = self._check_dim(embedder(query))
        client = self._require_client()
        flt = models.Filter(
            must=[
                models.FieldCondition(
                    key="embed_model", match=models.MatchValue(value=embed_model)
                )
            ]
        )
        try:
            hits = client.query_points(
                collection_name=self._config.collection,
                query=vec,
                query_filter=flt,
                limit=limit,
                with_payload=True,
            ).points
        except Exception as exc:  # noqa: BLE001 - surfaced loudly
            raise GenesisError(f"Qdrant recall_similar failed: {exc}") from exc

        out: list[tuple[Claim, float]] = []
        for h in hits:
            p = h.payload or {}
            claim = Claim(
                id=p["claim_id"],
                text=p["text"],
                sources=[_source_from_payload(s) for s in p.get("sources", [])],
                quote=p.get("quote"),
                status=ClaimStatus(p["status"]),
                confidence=p.get("confidence", 0.0),
                verification=[_source_from_payload(s) for s in p.get("verification", [])],
                produced_by=p.get("produced_by", ""),
                model=p.get("model", ""),
                created_at=datetime.fromisoformat(p["created_at"]),
            )
            out.append((claim, float(h.score)))
        return out


__all__ = [
    "Embedder",
    "QdrantConfig",
    "QdrantLedgerStore",
    "qdrant_available",
]
