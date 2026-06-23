# Depth-Audit: `src/gen/ledger/postgres.py` (T02)

**Verdikt: REAL.**

The deterministic, non-pool code paths (PostgresConfig.from_env + connect_kwargs, embed_dim, unsourced guards before _require_pool, dimension guard via public store_embedding) are genuine and match the documented contract exactly. No silent defaults. The PostgresLedgerStore satisfies the offline characterization without touching asyncpg or a live DB.

(This round-2 revision ensures the test uses *only public API* and proper env isolation for ctor tests, addressing review feedback while still covering the required contracts.)

## Headline-Claim (task spec + module docstring)

Exercise ONLY the deterministic non-database code in `postgres.py` (via public API only):
- `PostgresConfig.from_env()` resolves `GENESIS_DB_*` (DSN wins, documented defaults).
- `connect_kwargs()`: dsn precedence, socket omits port, TCP adds port, password only when set.
- `embed_dim` property reflects config.
- Fresh store (no `connect()`) makes `_require_pool`-backed methods (e.g. `ensure_run`) raise GenesisError.
- `add_claims`/`update_claim` raise `UnsourcedClaimError` on empty-sources claim **before** any pool access.
- Dimension validation is exercised via the public `store_embedding` path (raises loud before pool).

## Evidence (what the tests pin)

All assertions executed against the **real** module (no mocks of postgres.py internals except env via monkeypatch; *no private underscored symbols are imported or called*):

- `from_env` defaults + full env override (monkeypatch set/clear of DSN/HOST/PORT/NAME/USER/PASSWORD/EMBED_DIM) — 2 dedicated tests.
- `connect_kwargs` four cases (dsn wins, socket no-port, tcp+port+pw, pw only-when-set).
- `embed_dim` property + Hypothesis property test over embed_dim values.
- Dimension mismatch exercised via public `store_embedding(...)` (raises GenesisError before any pool).
- Fresh `PostgresLedgerStore(config=...)` without connect → GenesisError on `ensure_run`.
- Unsourced guards in `add_claims` and `update_claim` fire on tampered empty-sources claims **before** `_require_pool` (exact `UnsourcedClaimError`).
- dsn ctor (positional/kw) exercised with env isolation (monkeypatch) so from_env side-effects are controlled; public .embed_dim observed.

No edit to `src/gen/ledger/postgres.py` was required — all properties already hold (per "change nothing if correct" + 2026-06-23 decisions). This change touches only the test file and this audit (zero src/ files).

## Changes

- Added `tests/test_postgres_ledger_characterization.py` (new authoritative characterization test; legacy `test_ledger_postgres_integration.py` untouched).
- Added `docs/audit/DEPTH_AUDIT_postgres.md` (this file).
- `src/gen/ledger/postgres.py` — **no changes**.

## Tests

`tests/test_postgres_ledger_characterization.py` (new) + pre-existing core tests:
- Public-API tests (env/defaults, kwargs matrix, embed_dim + Hypothesis property, dim-via-public-embedding, fresh-store guard, two unsourced-before-pool negatives, isolated dsn-ctor).
- All pass using only the module under test + stdlib + Hypothesis (already declared) + pytest (no asyncpg, no live server).
- Uses real `Claim`/`SourceRef`/`SourceSupport` constructors (never invented fields).
- No private symbols (_*) accessed.

Command: `PYTHONPATH=src python3 -m pytest tests/test_postgres_ledger_characterization.py -q --tb=short`

## 4 Linsen

- **L1 (Wahrheit):** Every asserted behavior (env resolution, kwarg shaping, embed_dim, dim-via-public-embedding, early unsourced guards, loud no-connect) is executed live against the real public functions and raises exactly as documented. No fabricated values. Private helpers never asserted directly.
- **L2 (Drift):** Determinism of connect_kwargs shape and embed_dim is pinned (Hypothesis property + explicit examples). Config construction is side-effect free except for the tested env reads (now isolated in dsn-ctor test too).
- **L3 (Vollständigkeit/Naht):** The pure layer of the third provenance enforcement tier is covered via public surface only (config + early guards + embedding gate). The DB-dependent half remains in the integration test; the seam between `PostgresConfig` and `InMemoryLedgerStore` contract is untouched and compatible.
- **L4 (Realisierbarkeits):** Guards on dimension (public path), connect, and unsourced provenance are real and loud; no blanket NaN/inf guards added (per team decision scope). Property test + explicit negatives + env-isolated ctor test make the "fail loud, no silent default" contract falsifiable.

## Relation to GENESIS_PLATFORM_PLAN / HORIZON / decisions

Satisfies the offline-pure PostgresLedgerStore audit item (2026-06-23 decisions log). Contributes to honest durable ledger (A5 reproducibility via config + run_id, provenance triple-belt) without requiring a DB in the unit gate. The InMemory store remains the behavioural reference; this pins that the adapter's pure helpers match it.

**Result:** REAL. The deterministic surface of the durable ledger earns its description. No source modification (characterization only; round-2 fixes made test use strictly public API + env isolation for ctor; "harden" refers exclusively to test coverage + documentation, never code changes to postgres.py). This patch touches only test + audit (zero files under src/).

## BUILD_LOG consistency note
Per standing team decisions (BUILD_LOG.md deliberately OUT of per-task scope to avoid shared-file merge collisions across parallel worktrees), the full T02 entry lives here in the AUDIT (verdict + 4 Linsen + evidence). The integrator consolidates short entries into BUILD_LOG.md / docs/BUILD_LOG.md at merge time. This file (and the test) make no claim that a specific BUILD_LOG entry already exists in the root file for this task. No changes were made to src/gen/ledger/postgres.py.
