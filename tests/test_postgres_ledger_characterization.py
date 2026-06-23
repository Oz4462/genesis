"""Characterization test for the deterministic (offline-pure) parts of PostgresLedgerStore.

This pins exactly the contract described in the 2026-06-23 task: ONLY the code paths
that do not touch asyncpg or a DB pool. The integration test remains the one that
requires a live server.

All tests use real constructors from core.state and the module under test.
No source edits were required (all documented behavior already holds).

Property-based tests (Hypothesis) cover the round-trip and formatting invariants.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import GenesisError, UnsourcedClaimError  # noqa: E402
from gen.core.state import Claim, SourceRef, SourceSupport  # noqa: E402
from gen.ledger.postgres import (  # noqa: E402
    PostgresConfig,
    PostgresLedgerStore,
    _support_from_db,
    _support_to_db,
)


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
    assert cfg.user  # either $USER or "genesis"
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


# --- _support_to_db / _support_from_db round-trips and None default -----------

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
    """Round-trip + defaulting invariant: only CONTRADICTS is preserved exactly;
    None and SUPPORTS both map to the default 'supports' direction on the DB side
    and come back as SUPPORTS (the documented "scholar defaults to supports").
    """
    db_val = _support_to_db(support)
    back = _support_from_db(db_val)
    if support is SourceSupport.CONTRADICTS:
        assert db_val == "contradicts"
        assert back is SourceSupport.CONTRADICTS
    else:
        assert db_val == "supports"
        assert back is SourceSupport.SUPPORTS


# --- _check_dim, _to_pgvector, embed_dim property ----------------------------

def test_check_dim_returns_float_list_of_correct_length_and_raises_on_mismatch():
    cfg = PostgresConfig(
        dsn=None, host="h", port=1, database="d", user="u", password=None, embed_dim=3
    )
    store = PostgresLedgerStore(config=cfg)
    out = store._check_dim([1, 2.0, "3"])
    assert out == [1.0, 2.0, 3.0]
    assert isinstance(out, list)

    with pytest.raises(GenesisError, match="dimension"):
        store._check_dim([1.0, 2.0])  # wrong length


def test_to_pgvector_renders_pgvector_literal():
    lit = PostgresLedgerStore._to_pgvector([0, 1.5, -2.25])
    assert lit == "[0.0,1.5,-2.25]"
    assert lit.startswith("[") and lit.endswith("]")


def test_embed_dim_property_reflects_config():
    cfg = PostgresConfig(
        dsn=None, host="h", port=1, database="d", user="u", password=None, embed_dim=512
    )
    store = PostgresLedgerStore(config=cfg)
    assert store.embed_dim == 512


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
