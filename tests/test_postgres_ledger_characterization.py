"""Characterization test for the deterministic (offline-pure) parts of PostgresLedgerStore.

This pins exactly the contract described in the 2026-06-23 task (see spec):
ONLY the deterministic, non-database code (no asyncpg, no live server).
Uses public surface (from_env, connect_kwargs, embed_dim, guards on add/update/ensure,
dim via store_embedding) PLUS direct tests of the small pure helpers
_support_to_db/_support_from_db (roundtrips + None->'supports') and
_to_pgvector (literal render) because the task spec explicitly requires them
for offline coverage. The live-DB integration test is skipped in this gate,
so regression in support mapping or pgvector literal would otherwise go undetected.

All tests use real constructors from core.state and the module under test.
No source edits to postgres.py were required (all documented behavior already holds;
"harden" refers only to test coverage + docs).

Property-based tests (Hypothesis) cover round-trip and other invariants.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# hypothesis is a dev extra; importorskip prevents hard collection failure in envs without [dev]
# (addresses latent coupling while keeping property tests authoritative for this characterization).
pytest.importorskip("hypothesis", reason="hypothesis (dev extra) required for property-based characterization tests")
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import GenesisError, UnsourcedClaimError  # noqa: E402
from gen.core.state import Claim, SourceRef, SourceSupport  # noqa: E402
from gen.ledger.postgres import PostgresConfig, PostgresLedgerStore, _support_from_db, _support_to_db  # noqa: E402


def run(coro):
    """Run an async coroutine deterministically (stdlib only)."""
    return asyncio.run(coro)


def _src(url: str = "https://example.org/s", support: SourceSupport = SourceSupport.SUPPORTS) -> SourceRef:
    return SourceRef(url_or_id=url, retrieved=True, support=support)


def _claim(cid: str, text: str = "a fact", url: str = "https://example.org/s") -> Claim:
    return Claim(id=cid, text=text, sources=[_src(url)], produced_by="scholar")


# --- PostgresConfig.from_env() env resolution + documented defaults ----------

def test_from_env_defaults_when_unset(monkeypatch):
    """Unset GENESIS_DB_* yield the documented peer-auth local defaults."""
    for key in [
        "GENESIS_DB_DSN",
        "GENESIS_DB_HOST",
        "GENESIS_DB_PORT",
        "GENESIS_DB_NAME",
        "GENESIS_DB_USER",
        "GENESIS_DB_PASSWORD",
        "GENESIS_EMBED_DIM",
    ]:
        monkeypatch.delenv(key, raising=False)
    # also ensure USER does not interfere with default_user logic in a surprising way
    monkeypatch.delenv("USER", raising=False)

    cfg = PostgresConfig.from_env()
    assert cfg.dsn is None
    assert cfg.host == "/var/run/postgresql"
    assert cfg.port == 5432
    assert cfg.database == "genesis"
    # After clearing USER + GENESIS_DB_USER, the documented fallback is exactly "genesis"
    # (see PostgresConfig.from_env: default_user = os.environ.get("USER") or "genesis")
    assert cfg.user == "genesis"
    assert cfg.password is None
    assert cfg.embed_dim == 768


def test_from_env_resolves_all_genesis_vars(monkeypatch):
    """Explicit GENESIS_DB_* values are used (DSN does not suppress other reads)."""
    monkeypatch.setenv("GENESIS_DB_DSN", "postgresql://user:pass@host:5433/dbname")
    monkeypatch.setenv("GENESIS_DB_HOST", "db.local")
    monkeypatch.setenv("GENESIS_DB_PORT", "5544")
    monkeypatch.setenv("GENESIS_DB_NAME", "gbase")
    monkeypatch.setenv("GENESIS_DB_USER", "guser")
    monkeypatch.setenv("GENESIS_DB_PASSWORD", "gpw")
    monkeypatch.setenv("GENESIS_EMBED_DIM", "1024")

    cfg = PostgresConfig.from_env()
    assert cfg.dsn == "postgresql://user:pass@host:5433/dbname"
    assert cfg.host == "db.local"
    assert cfg.port == 5544
    assert cfg.database == "gbase"
    assert cfg.user == "guser"
    assert cfg.password == "gpw"
    assert cfg.embed_dim == 1024


# --- connect_kwargs() dsn precedence, socket vs TCP, password presence --------

def test_connect_kwargs_dsn_wins_over_parts():
    cfg = PostgresConfig(
        dsn="postgresql://x@y/z",
        host="ignored",
        port=1,
        database="ignored",
        user="ignored",
        password="ignored",
        embed_dim=8,
    )
    assert cfg.connect_kwargs() == {"dsn": "postgresql://x@y/z"}


def test_connect_kwargs_omits_port_for_unix_socket():
    cfg = PostgresConfig(
        dsn=None,
        host="/var/run/postgresql",
        port=5432,
        database="genesis",
        user="genesis",
        password=None,
        embed_dim=768,
    )
    kw = cfg.connect_kwargs()
    assert "dsn" not in kw
    assert "port" not in kw
    assert kw["host"] == "/var/run/postgresql"


def test_connect_kwargs_includes_port_for_tcp_host():
    cfg = PostgresConfig(
        dsn=None,
        host="127.0.0.1",
        port=6543,
        database="genesis",
        user="genesis",
        password=None,
        embed_dim=768,
    )
    kw = cfg.connect_kwargs()
    assert kw["port"] == 6543
    assert "password" not in kw


def test_connect_kwargs_includes_password_only_when_set():
    cfg_no = PostgresConfig(
        dsn=None, host="h", port=1, database="d", user="u", password=None, embed_dim=1
    )
    assert "password" not in cfg_no.connect_kwargs()

    cfg_yes = PostgresConfig(
        dsn=None, host="h", port=1, database="d", user="u", password="secret", embed_dim=1
    )
    assert cfg_yes.connect_kwargs()["password"] == "secret"


# --- _support_to_db / _support_from_db round-trips (spec-required for offline) ---
# These pure helpers implement the documented mapping (None/SUPPORTS -> 'supports',
# CONTRADICTS -> 'contradicts'). Per task spec they must be asserted in the offline
# char test: the only other exercise is inside the live-DB integration test
# (which is skipped in this gate). Direct coverage here prevents silent regression
# in provenance direction when no DB is present. (Small, deterministic, no side effects.)

def test_support_to_db_maps_none_and_supports_to_supports():
    assert _support_to_db(None) == "supports"
    assert _support_to_db(SourceSupport.SUPPORTS) == "supports"


def test_support_to_db_maps_contradicts():
    assert _support_to_db(SourceSupport.CONTRADICTS) == "contradicts"


def test_support_from_db_round_trips():
    assert _support_from_db("supports") is SourceSupport.SUPPORTS
    assert _support_from_db("contradicts") is SourceSupport.CONTRADICTS


@settings(max_examples=30)
@given(
    support=st.sampled_from([None, SourceSupport.SUPPORTS, SourceSupport.CONTRADICTS])
)
def test_support_roundtrip_property(support):
    """Round-trip + defaulting invariant (property-based per spec + A5):
    Only CONTRADICTS is preserved exactly; None and SUPPORTS map to the default
    'supports' (as documented for scholar sources).
    """
    db_val = _support_to_db(support)
    back = _support_from_db(db_val)
    if support is SourceSupport.CONTRADICTS:
        assert db_val == "contradicts"
        assert back is SourceSupport.CONTRADICTS
    else:
        assert db_val == "supports"
        assert back is SourceSupport.SUPPORTS


# --- _to_pgvector literal (spec-required for offline) ---
# The static helper produces the exact pgvector text literal form used in SQL.
# Spec requires asserting the '[v0,v1,...]' render. Only other path is live
# embedding in integration (skipped offline), so must cover here for the gate.

def test_to_pgvector_renders_pgvector_literal():
    lit = PostgresLedgerStore._to_pgvector([0, 1.5, -2.25])
    assert lit == "[0.0,1.5,-2.25]"
    assert lit.startswith("[") and lit.endswith("]")


# --- Backward-compat ctor PostgresLedgerStore(dsn=...) ------------------------
# Used by scripts/postgres_smoke.py: PostgresLedgerStore(TEST_DSN) (positional dsn path).
# Must set the dsn on the internal config so connect_kwargs() uses the full DSN and
# the rest of the class works without re-reading env.

def test_postgresledgerstore_dsn_ctor_backward_compat(monkeypatch):
    """PostgresLedgerStore(dsn=...) (the historic positional/kwarg path) accepts dsn and
    uses PostgresConfig.from_env() + override internally.

    The test is made hermetic with monkeypatch (unlike before) so that from_env inside the
    ctor sees only documented defaults, not whatever real env is present in the test runner.
    We only assert public surface (embed_dim from the controlled from_env); the 'dsn wins'
    logic for connect_kwargs is already covered by the public PostgresConfig tests above.
    The ctor with dsn is the path used by scripts/postgres_smoke.py.
    """
    # isolate: make from_env() inside ctor see clean defaults (no leakage from real env)
    for key in [
        "GENESIS_DB_DSN", "GENESIS_DB_HOST", "GENESIS_DB_PORT", "GENESIS_DB_NAME",
        "GENESIS_DB_USER", "GENESIS_DB_PASSWORD", "GENESIS_EMBED_DIM",
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("USER", raising=False)

    # positional (most common in smoke scripts) - must not explode, produces usable store
    store1 = PostgresLedgerStore("postgresql://u@h/db1")
    assert store1.embed_dim == 768  # default after clean from_env

    # explicit kwarg form
    store2 = PostgresLedgerStore(dsn="postgresql://u@h/db2")
    assert store2.embed_dim == 768

    # explicit config= (public) still works alongside
    cfg = PostgresConfig(dsn=None, host="h", port=1, database="d", user="u", password=None, embed_dim=64)
    store3 = PostgresLedgerStore(config=cfg)
    assert store3.embed_dim == 64


# --- dimension validation (exercised via public path) + other helpers covered above ---
# _check_dim is exercised via public store_embedding (before pool). The support
# mapping and _to_pgvector literal are tested directly above per explicit task spec
# (offline regression protection for helpers whose only other use is in skipped
# integration test).

def test_embed_dim_property_reflects_config():
    cfg = PostgresConfig(
        dsn=None, host="h", port=1, database="d", user="u", password=None, embed_dim=512
    )
    store = PostgresLedgerStore(config=cfg)
    assert store.embed_dim == 512


# --- property-based test on public API (keeps Hypothesis usage for invariants) ---

@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(embed_dim=st.integers(min_value=1, max_value=4096))
def test_embed_dim_from_env_and_store_property(monkeypatch, embed_dim):
    """Public API invariant: whatever GENESIS_EMBED_DIM (or default) is used to build
    PostgresConfig.from_env(), a store constructed from it exposes exactly that via
    the public .embed_dim property. (A5-style determinism of the config surface.)
    """
    monkeypatch.delenv("GENESIS_EMBED_DIM", raising=False)
    monkeypatch.setenv("GENESIS_EMBED_DIM", str(embed_dim))
    cfg = PostgresConfig.from_env()
    store = PostgresLedgerStore(config=cfg)
    assert store.embed_dim == embed_dim


def test_dimension_mismatch_raises_in_public_store_embedding_path():
    """The dimension guard (previously _check_dim) is exercised by the public
    store_embedding entry point and raises *before* any pool access.
    This keeps the test on public contract while proving the loud error for
    mismatched embedder (no silent wrong vector).
    """
    cfg = PostgresConfig(
        dsn=None, host="h", port=1, database="d", user="u", password=None, embed_dim=3
    )
    store = PostgresLedgerStore(config=cfg)

    def bad_embedder(text: str) -> list[float]:
        return [0.1, 0.2]  # wrong length

    with pytest.raises(GenesisError, match="dimension"):
        run(store.store_embedding("c1", "some text", bad_embedder, embed_model="test"))
    # note: _require_pool is never reached because check fails first


# --- Fresh store (no connect) requires pool loudly on backed methods ----------

def test_fresh_store_raises_on_require_pool_backed_methods():
    cfg = PostgresConfig(
        dsn=None, host="/s", port=1, database="d", user="u", password=None, embed_dim=8
    )
    store = PostgresLedgerStore(config=cfg)
    # ensure_run is a representative _require_pool user
    with pytest.raises(GenesisError, match="connect\\(\\) was not called"):
        run(store.ensure_run("run-1", "question?", "cfg-hash"))


# --- add_claims / update_claim raise Unsourced BEFORE any pool access ---------
# (proves the guard is not behind the DB connection requirement)

def test_add_claims_raises_unsourced_before_pool_access():
    cfg = PostgresConfig(
        dsn=None, host="/s", port=1, database="d", user="u", password=None, embed_dim=8
    )
    store = PostgresLedgerStore(config=cfg)

    c = _claim("c1")
    # post-construction tamper (as done in the InMemory ledger tests)
    c.sources = []
    with pytest.raises(UnsourcedClaimError):
        run(store.add_claims("r1", [c]))


def test_update_claim_raises_unsourced_before_pool_access():
    cfg = PostgresConfig(
        dsn=None, host="/s", port=1, database="d", user="u", password=None, embed_dim=8
    )
    store = PostgresLedgerStore(config=cfg)

    c = _claim("c1")
    c.sources = []
    with pytest.raises(UnsourcedClaimError):
        run(store.update_claim(c))


# (No extra test for empty list: the implementation requires the pool for the
# transaction path even on [], which is fine and outside the "unsourced guard
# before pool" contract we are characterizing.)
