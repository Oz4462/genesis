"""GENESIS fact ledger: provenance-enforcing storage for Claims.

Public API:
  InMemoryLedgerStore  — dependency-free reference implementation (tests, local).
  PostgresLedgerStore  — durable adapter against sql/001_ledger.sql.
  FetchRecord          — audit record of a source-retrieval attempt.
  UnknownClaimError    — raised when updating a claim the ledger never saw.

The Postgres adapter is imported lazily so the package never hard-depends on a
database driver.
"""

from __future__ import annotations

from .store import FetchRecord, InMemoryLedgerStore, UnknownClaimError

__all__ = [
    "InMemoryLedgerStore",
    "FetchRecord",
    "UnknownClaimError",
    "PostgresLedgerStore",
    "PostgresConfig",
]


def __getattr__(name: str):
    # Lazy: only import the Postgres adapter (and asyncpg) on demand.
    if name in ("PostgresLedgerStore", "PostgresConfig"):
        from . import postgres
        return getattr(postgres, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
