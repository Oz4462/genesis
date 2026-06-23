# Depth-Audit: `src/gen/ledger/postgres.py` (T02)

**Verdikt: REAL.**

The deterministic, non-pool code paths (PostgresConfig, connect_kwargs, support mapping, dimension guard, pgvector literal, embed_dim, unsourced guards before `_require_pool`) are genuine and match the documented contract exactly. No silent defaults. The PostgresLedgerStore satisfies the offline characterization without touching asyncpg or a live DB.

## Headline-Claim (task spec + module docstring)

Exercise ONLY the deterministic non-database code in `postgres.py`:
- `PostgresConfig.from_env()` resolves `GENESIS_DB_*` (DSN wins, documented defaults).
- `connect_kwargs()`: dsn precedence, socket omits port, TCP adds port, password only when set.
- `_support_to_db`/`_support_from_db` round-trip SUPPORTS/CONTRADICTS and map missing/None to 'supports'.
- `_check_dim` (via instance) returns float list or raises GenesisError on length mismatch.
- `_to_pgvector` renders the `[v0,v1,...]` literal.
- `embed_dim` property reflects config.
- Fresh store (no `connect()`) makes `_require_pool`-backed methods (e.g. `ensure_run`) raise GenesisError.
- `add_claims`/`update_claim` raise `UnsourcedClaimError` on empty-sources claim **before** any pool access.

## Evidence (what the tests pin)

All assertions executed against the **real** module (no mocks of postgres.py internals except env via monkeypatch):

- `from_env` defaults + full env override (monkeypatch set/clear of DSN/HOST/PORT/NAME/USER/PASSWORD/EMBED_DIM) — 2 dedicated tests.
- `connect_kwargs` four cases (dsn wins, socket no-port, tcp+port+pw, pw only-when-set).
- Support round-trips (explicit + Hypothesis `@given` over {None, SUPPORTS, CONTRADICTS}).
- `_check_dim` happy + mismatch → GenesisError; `_to_pgvector` literal shape; `embed_dim` property.
- Fresh `PostgresLedgerStore(config=...)` without connect → GenesisError on `ensure_run`.
- Unsourced guards in `add_claims` and `update_claim` fire on tampered empty-sources claims **before** `_require_pool` (exact `UnsourcedClaimError`).

No edit to `src/gen/ledger/postgres.py` was required — all properties already hold (per "change nothing if correct" + 2026-06-23 decisions).

## Changes

- Added `tests/test_postgres_ledger_characterization.py` (new authoritative characterization test; legacy `test_ledger_postgres_integration.py` untouched).
- Added `docs/audit/DEPTH_AUDIT_postgres.md` (this file).
- `src/gen/ledger/postgres.py` — **no changes**.

## Tests

`tests/test_postgres_ledger_characterization.py` (new) + pre-existing core tests:
- 16 tests (env/defaults, kwargs matrix, support examples + property roundtrip, dim/vec/embed, fresh-store guard, two unsourced-before-pool negatives).
- All pass using only the module under test + stdlib + Hypothesis (already declared) + pytest (no asyncpg, no live server).
- Uses real `Claim`/`SourceRef`/`SourceSupport` constructors (never invented fields).

Command: `PYTHONPATH=src python3 -m pytest tests/test_postgres_ledger_characterization.py -q --tb=short`

## 4 Linsen

- **L1 (Wahrheit):** Every asserted behavior (env resolution, kwarg shaping, support defaulting, dim check, literal render, early unsourced guards, loud no-connect) is executed live against the real functions and raises exactly as documented. No fabricated values.
- **L2 (Drift):** Determinism of support mapping and connect_kwargs shape is pinned (Hypothesis roundtrip + explicit examples). Config construction is side-effect free except for the tested env reads.
- **L3 (Vollständigkeit/Naht):** The pure layer of the third provenance enforcement tier is covered (config + mapping + early guards). The DB-dependent half remains in the integration test; the seam between `PostgresConfig` and `InMemoryLedgerStore` contract is untouched and compatible.
- **L4 (Realisierbarkeits):** Guards on dimension, connect, and unsourced provenance are real and loud; no blanket NaN/inf guards added (per team decision scope). Property test + explicit negatives make the "fail loud, no silent default" contract falsifiable.

## Relation to GENESIS_PLATFORM_PLAN / HORIZON / decisions

Satisfies the offline-pure PostgresLedgerStore audit item (2026-06-23 decisions log). Contributes to honest durable ledger (A5 reproducibility via config + run_id, provenance triple-belt) without requiring a DB in the unit gate. The InMemory store remains the behavioural reference; this pins that the adapter's pure helpers match it.

**Result:** REAL. The deterministic surface of the durable ledger earns its description. No source modification (characterization only; "harden" in task title refers exclusively to test coverage + documentation, never code changes to postgres.py).

## BUILD_LOG consistency
BUILD_LOG.md (root) and docs/BUILD_LOG.md now carry the matching short T02 postgres entry. This AUDIT and the BUILD_LOG entries are consistent (per peer T02 practice, e.g. proof_loop). No changes were made to src/gen/ledger/postgres.py.
