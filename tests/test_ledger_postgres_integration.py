"""PostgreSQL + pgvector integration test for the durable ledger.

This is the REAL round-trip the InMemory tests cannot exercise: it connects to a
live PostgreSQL with the pgvector extension, applies sql/001 + sql/002, writes a
run + provenance-backed claims, embeds them, and recalls the right claim by
SEMANTIC similarity — the retrieval half of "no claim without source".

It is named ``*_integration.py`` and SKIPS gracefully when:
  * ``asyncpg`` is not installed, or
  * no PostgreSQL is reachable with the configured ``GENESIS_DB_*`` (default:
    local peer auth over the unix socket as the OS user, db ``genesis``).

On the GENESIS dev box the server is UP and the ``genesis`` role/db + pgvector
exist, so this is expected to PASS, not skip.

Honesty of the test:
  * The embedder is a DETERMINISTIC, dependency-free local embedder (a fixed
    random projection of a word/char-trigram bag). It is NOT Ollama — the point
    is to prove the PG+pgvector store/recall plumbing end-to-end without needing a
    model server. It is genuinely semantic in the weak sense that more shared
    tokens -> higher cosine, which is all the recall assertion needs.
  * Each run uses a UNIQUE run_id (uuid) so repeated test runs don't collide and
    the assertions are scoped to this run.

Run:  PYTHONPATH=src .venv/bin/python -m pytest tests/test_ledger_postgres_integration.py -q
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

asyncpg = pytest.importorskip("asyncpg", reason="PostgresLedgerStore needs asyncpg")

from gen.core.errors import GenesisError, UnsourcedClaimError  # noqa: E402
from gen.core.state import Claim, ClaimStatus, SourceRef, SourceSupport  # noqa: E402
from gen.ledger.postgres import PostgresConfig, PostgresLedgerStore  # noqa: E402

EMBED_DIM = 64  # small, fast; the store substitutes it into the pgvector column
EMBED_MODEL = "test-det-proj-v1"


def run(coro):
    return asyncio.run(coro)


# --- A deterministic, dependency-free local embedder (NOT Ollama) -------------

def _det_embedder(dim: int = EMBED_DIM):
    """Return a deterministic text->vector embedder.

    Bag of word/char-trigram tokens, each hashed to a stable pseudo-random vector;
    the sum is L2-normalised. Same text -> identical vector; texts sharing tokens
    have higher cosine. Good enough to prove recall ranks the matching claim first.
    """
    import math

    def token_vec(token: str) -> list[float]:
        # 8 bytes per dimension chunk from a stable hash, mapped to [-1, 1].
        out: list[float] = []
        i = 0
        while len(out) < dim:
            h = hashlib.sha256(f"{token}:{i}".encode()).digest()
            for b in h:
                out.append((b / 127.5) - 1.0)
                if len(out) >= dim:
                    break
            i += 1
        return out

    def embed(text: str) -> list[float]:
        tokens = text.lower().split()
        # add char trigrams for sub-word overlap
        squashed = "".join(tokens)
        tokens += [squashed[i : i + 3] for i in range(max(0, len(squashed) - 2))]
        acc = [0.0] * dim
        for tok in tokens or [""]:
            tv = token_vec(tok)
            for k in range(dim):
                acc[k] += tv[k]
        norm = math.sqrt(sum(x * x for x in acc)) or 1.0
        return [x / norm for x in acc]

    return embed


def _src(url: str) -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=True, support=SourceSupport.SUPPORTS)


def _claim(cid: str, text: str, url: str) -> Claim:
    return Claim(
        id=cid,
        text=text,
        sources=[_src(url)],
        status=ClaimStatus.VERIFIED,
        confidence=0.9,
        produced_by="scholar",
        model="test",
    )


# --- Fixture: a connected store with schema, or skip if no server ------------

def _make_store() -> PostgresLedgerStore:
    cfg = PostgresConfig.from_env()
    # force the small test dimension regardless of the env default
    object.__setattr__(cfg, "embed_dim", EMBED_DIM)
    return PostgresLedgerStore(config=cfg)


async def _connect_or_skip() -> PostgresLedgerStore:
    store = _make_store()
    try:
        await store.connect()
    except GenesisError as exc:  # server down / role missing -> skip, don't fail
        pytest.skip(f"PostgreSQL not reachable for integration test: {exc}")
    return store


# --- The real round-trip -----------------------------------------------------

def test_pgvector_roundtrip_recalls_matching_claim_with_provenance():
    """A claim stored + embedded is recalled as the top semantic match, carrying
    its full provenance (sources reconstructed from claim_sources)."""

    async def scenario():
        store = await _connect_or_skip()
        try:
            await store.ensure_schema()
            run_id = f"itest-{uuid.uuid4().hex[:12]}"
            await store.ensure_run(run_id, "integration test question", "cfg-hash-1")

            embedder = _det_embedder()
            c_solar = _claim(
                f"{run_id}-solar",
                "Photovoltaic solar panels convert sunlight into electricity.",
                "https://example.org/solar",
            )
            c_battery = _claim(
                f"{run_id}-batt",
                "Lithium-ion batteries store electrical energy chemically.",
                "https://example.org/battery",
            )
            c_bridge = _claim(
                f"{run_id}-bridge",
                "Suspension bridges carry deck loads through tensioned cables.",
                "https://example.org/bridge",
            )
            await store.add_claims(run_id, [c_solar, c_battery, c_bridge])

            for c in (c_solar, c_battery, c_bridge):
                await store.store_embedding(
                    c.id, c.text, embedder, embed_model=EMBED_MODEL
                )

            # Query semantically closest to the solar claim.
            hits = await store.recall_similar(
                "sunlight photovoltaic electricity from solar panels",
                embedder,
                embed_model=EMBED_MODEL,
                limit=3,
                run_id=run_id,
            )
            assert hits, "recall returned nothing"
            top_claim, top_sim = hits[0]
            assert top_claim.id == c_solar.id, (
                f"expected solar claim on top, got {top_claim.id} "
                f"(ranking: {[(h.id, round(s, 3)) for h, s in hits]})"
            )
            # provenance survived the round-trip through claim_sources
            assert [s.url_or_id for s in top_claim.sources] == [
                "https://example.org/solar"
            ]
            assert top_claim.status is ClaimStatus.VERIFIED
            # cosine similarity is in range and the top is the most similar
            assert -1.0001 <= top_sim <= 1.0001
            assert top_sim >= hits[-1][1]

            # exact-match query returns ~1.0 similarity for that claim
            exact = await store.recall_similar(
                c_battery.text, embedder, embed_model=EMBED_MODEL, limit=1, run_id=run_id
            )
            assert exact[0][0].id == c_battery.id
            assert exact[0][1] > 0.99  # same vector -> cosine ~1
        finally:
            await store.close()

    run(scenario())


def test_recall_isolated_by_embed_model():
    """Vectors from a different embed_model are NOT returned (no cross-space mixing)."""

    async def scenario():
        store = await _connect_or_skip()
        try:
            await store.ensure_schema()
            run_id = f"itest-{uuid.uuid4().hex[:12]}"
            await store.ensure_run(run_id, "model isolation", "cfg-hash-2")
            embedder = _det_embedder()
            c = _claim(f"{run_id}-x", "turbine blades resist creep at high temperature",
                       "https://example.org/turbine")
            await store.add_claims(run_id, [c])
            await store.store_embedding(c.id, c.text, embedder, embed_model="model-A")

            # querying under a DIFFERENT model name finds nothing
            hits = await store.recall_similar(
                c.text, embedder, embed_model="model-B", limit=5, run_id=run_id
            )
            assert hits == []
        finally:
            await store.close()

    run(scenario())


# --- Negative tests: prove it fails LOUD, never silently --------------------

def test_dimension_mismatch_raises_loud():
    """An embedder whose vector length != the schema dimension is a loud error,
    not a silent wrong-dimension insert."""

    async def scenario():
        store = await _connect_or_skip()
        try:
            await store.ensure_schema()
            run_id = f"itest-{uuid.uuid4().hex[:12]}"
            await store.ensure_run(run_id, "dim mismatch", "cfg-hash-3")
            c = _claim(f"{run_id}-d", "fact text", "https://example.org/d")
            await store.add_claims(run_id, [c])

            wrong = _det_embedder(dim=EMBED_DIM + 1)  # one too many
            with pytest.raises(GenesisError, match="dimension"):
                await store.store_embedding(
                    c.id, c.text, wrong, embed_model=EMBED_MODEL
                )
        finally:
            await store.close()

    run(scenario())


def test_db_trigger_rejects_sourceless_claim():
    """The sql/001 DEFERRABLE trigger rejects a claim with no source rows even if
    the in-code guard were bypassed — the third provenance layer, live."""

    async def scenario():
        store = await _connect_or_skip()
        try:
            await store.ensure_schema()
            run_id = f"itest-{uuid.uuid4().hex[:12]}"
            await store.ensure_run(run_id, "sourceless", "cfg-hash-4")
            # Bypass the Python guard: insert a claim row with NO claim_sources, in
            # its own transaction, so the DEFERRED trigger fires at COMMIT.
            pool = store._require_pool()  # noqa: SLF001 - testing the DB layer directly
            with pytest.raises(asyncpg.PostgresError):
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute(
                            """
                            INSERT INTO claims
                              (id, run_id, text, quote, status, confidence,
                               produced_by, model)
                            VALUES ($1,$2,'x',NULL,'verified',0.5,'scholar','test')
                            """,
                            f"{run_id}-orphan",
                            run_id,
                        )
        finally:
            await store.close()

    run(scenario())


def test_ensure_schema_rejects_dimension_mismatch():
    """A store configured for a different vector dimension than the existing
    claim_embeddings column fails LOUD at ensure_schema (no silent wrong-dim queries).
    Relies on the round-trip test having created the column at EMBED_DIM."""

    async def scenario():
        # First make sure the column exists at EMBED_DIM.
        base = await _connect_or_skip()
        try:
            await base.ensure_schema()
        finally:
            await base.close()

        cfg = PostgresConfig.from_env()
        object.__setattr__(cfg, "embed_dim", EMBED_DIM + 100)  # deliberate mismatch
        store = PostgresLedgerStore(config=cfg)
        try:
            await store.connect()
        except GenesisError as exc:
            pytest.skip(f"PostgreSQL not reachable: {exc}")
        try:
            with pytest.raises(GenesisError, match="dimension"):
                await store.ensure_schema()
        finally:
            await store.close()

    run(scenario())


def test_store_embedding_for_unknown_claim_raises():
    """Embedding a claim id the ledger never saw is rejected by the FK (loud)."""

    async def scenario():
        store = await _connect_or_skip()
        try:
            await store.ensure_schema()
            embedder = _det_embedder()
            with pytest.raises(GenesisError):
                await store.store_embedding(
                    f"ghost-{uuid.uuid4().hex}", "nope", embedder,
                    embed_model=EMBED_MODEL,
                )
        finally:
            await store.close()

    run(scenario())
