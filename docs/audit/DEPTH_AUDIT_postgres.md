# Depth-Audit: `src/gen/ledger/postgres.py` (T02)

**Verdikt: REAL.**

The deterministic, non-pool code paths (PostgresConfig.from_env + connect_kwargs, embed_dim, unsourced guards before _require_pool, dimension guard via public store_embedding, plus the small pure helpers _support_to_db/_support_from_db and _to_pgvector) are genuine and match the documented contract exactly. No silent defaults. The PostgresLedgerStore satisfies the offline characterization without touching asyncpg or a live DB.

Direct asserts on the pure helpers are present per the task spec (they implement the listed behaviors; their only other exercise is inside the live-DB integration test which is skipped in the offline gate). This round-3 revision adds back the spec-required _support round-trips (incl. property test) and _to_pgvector literal render.

## Headline-Claim (task spec + module docstring)

Exercise ONLY the deterministic non-database code in `postgres.py`:
- `PostgresConfig.from_env()` resolves `GENESIS_DB_*` (DSN wins, documented defaults).
- `connect_kwargs()`: dsn precedence, socket omits port, TCP adds port, password only when set.
- `embed_dim` property reflects config.
- Fresh store (no `connect()`) makes `_require_pool`-backed methods (e.g. `ensure_run`) raise GenesisError.
- `add_claims`/`update_claim` raise `UnsourcedClaimError` on empty-sources claim **before** any pool access.
- Dimension validation exercised via public `store_embedding` path (raises before pool).
- _support_to_db/_support_from_db round-trips (SUPPORTS/CONTRADICTS + None->'supports') and _to_pgvector literal render (spec-required for offline coverage).

## Evidence (what the tests pin)

All assertions executed against the **real** module (no mocks of postgres.py internals except env via monkeypatch):

- `from_env` defaults + full env override (monkeypatch set/clear ...) — 2 tests.
- `connect_kwargs` matrix (dsn wins, socket omits port, TCP includes, pw conditional).
- `embed_dim` + Hypothesis property test.
- Dimension mismatch via public store_embedding (before pool).
- Fresh store no-connect → GenesisError on ensure_run (public).
- Unsourced before pool on add/update (public, using tampered Claim).
- dsn ctor (positional + kw) with monkeypatch env isolation (hermetic).
- _support_to_db/_support_from_db: explicit + @given property roundtrip (None/SUPPORTS/CONTRADICTS).
- _to_pgvector: renders exact '[v0,v1,...]' literal.

These helper asserts are required by the task spec for this offline char test (integration paths skipped here). No edit to `src/gen/ledger/postgres.py`. This change touches only the test file and this audit (zero src/ files).

## Changes

- Added `tests/test_postgres_ledger_characterization.py` (new authoritative characterization test; legacy `test_ledger_postgres_integration.py` untouched).
- Added `docs/audit/DEPTH_AUDIT_postgres.md` (this file).
- `src/gen/ledger/postgres.py` — **no changes**.

## Tests

`tests/test_postgres_ledger_characterization.py` (new) + pre-existing core tests:
- from_env, connect_kwargs, embed_dim + property test, dim via public embedding, fresh-store/unsourced guards, dsn ctor (hermetic).
- Plus spec-required direct coverage: _support_* roundtrips (examples + @given property), _to_pgvector literal.
- All pass using only the module under test + stdlib + Hypothesis + pytest (no asyncpg, no live server).
- Uses real constructors. (Direct helper tests per task spec for offline gate.)

Command: `PYTHONPATH=src python3 -m pytest tests/test_postgres_ledger_characterization.py -q --tb=short`

## 4 Linsen

- **L1 (Wahrheit):** All listed behaviors (incl. spec-mandated _support roundtrips + _to_pgvector literal) executed live on real code. Raises exactly as documented. No fabricated values.
- **L2 (Drift):** Determinism (support property + connect/embed) pinned via Hypothesis + examples. Env reads isolated in ctor tests.
- **L3 (Vollständigkeit/Naht):** Offline contract fully covered (public + the pure helpers required by spec because integration is skipped here). DB half remains in integration; seams compatible.
- **L4 (Realisierbarkeits):** Guards real+loud; scoped (no blanket); property tests + negatives + hermetic ctor. Falsifiable.

## Relation to GENESIS_PLATFORM_PLAN / HORIZON / decisions

Satisfies the offline-pure PostgresLedgerStore audit item (2026-06-23 decisions log). Contributes to honest durable ledger (A5 reproducibility via config + run_id, provenance triple-belt) without requiring a DB in the unit gate. The InMemory store remains the behavioural reference; this pins that the adapter's pure helpers match it.

**Result:** REAL. The deterministic surface of the durable ledger earns its description. No source modification (characterization only; this round adds the spec-required helper asserts for _support and _to_pgvector to make the offline gate complete; "harden" refers exclusively to test coverage + documentation, never code changes to postgres.py). This patch touches only test + audit (zero files under src/).

## BUILD_LOG consistency note
Per standing team decisions (BUILD_LOG.md deliberately OUT of per-task scope to avoid shared-file merge collisions across parallel worktrees), the full T02 entry lives here in the AUDIT (verdict + 4 Linsen + evidence). The integrator consolidates short entries into BUILD_LOG.md / docs/BUILD_LOG.md at merge time. This file (and the test) make no claim that a specific BUILD_LOG entry already exists in the root file for this task. No changes were made to src/gen/ledger/postgres.py.
