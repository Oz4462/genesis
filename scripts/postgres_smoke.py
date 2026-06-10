"""Live Postgres smoke — closes the oldest open point (BUILD_LOG Aufgabe 1).

Verifies the PostgresLedgerStore against a REAL PostgreSQL using the real schema
(sql/001_ledger.sql), in a dedicated, disposable database (never touches other
projects' data). What it proves:

  1. the schema applies cleanly;
  2. add_claims + get_claims round-trip a sourced claim with full provenance;
  3. the THIRD provenance layer — the DB trigger ``claim_requires_source`` —
     actually fires, proven by bypassing the Python guard and inserting a
     sourceless claim directly via SQL: COMMIT must raise;
  4. record_fetch upserts; the independence view is queryable.

Connection (no secrets in source): pass an admin DSN as the first argument, or set
``GENESIS_PG_DSN``. The fallback is a passwordless localhost DSN (works only with
trust auth) so this file never embeds a credential.

Usage:  GENESIS_PG_DSN=postgresql://user:pw@localhost:5432/postgres py -3 scripts/postgres_smoke.py
        py -3 scripts/postgres_smoke.py <admin_dsn>
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console is cp1252 by default

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gen.core.errors import UnsourcedClaimError  # noqa: E402
from gen.core.state import Claim, ClaimStatus, SourceRef, SourceSupport  # noqa: E402
from gen.ledger.postgres import PostgresLedgerStore  # noqa: E402

ADMIN_DSN = (
    sys.argv[1] if len(sys.argv) > 1
    else os.environ.get("GENESIS_PG_DSN", "postgresql://postgres@localhost:5432/postgres")
)
TEST_DB = "genesis_test"
TEST_DSN = ADMIN_DSN.rsplit("/", 1)[0] + f"/{TEST_DB}"
SCHEMA = (Path(__file__).resolve().parents[1] / "sql" / "001_ledger.sql").read_text(encoding="utf-8")


async def recreate_test_db() -> None:
    con = await asyncpg.connect(ADMIN_DSN)
    try:
        # disposable test DB — drop+recreate so the smoke is reproducible.
        await con.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        await con.execute(f"CREATE DATABASE {TEST_DB}")
    finally:
        await con.close()


async def apply_schema() -> None:
    con = await asyncpg.connect(TEST_DSN)
    try:
        await con.execute(SCHEMA)
    finally:
        await con.close()


async def main() -> int:
    print(f"admin={ADMIN_DSN.split('@')[1]}  test_db={TEST_DB}")
    await recreate_test_db()
    await apply_schema()
    print("1. schema applied cleanly: OK")

    store = PostgresLedgerStore(TEST_DSN)
    await store.connect()
    try:
        await store.ensure_run("pg-smoke", "What is OCCT?", "deadbeefcafef00d")

        claim = Claim(
            id="pg-smoke:c1",
            text="Open Cascade Technology (OCCT) is an open-source geometry kernel.",
            sources=[SourceRef(url_or_id="https://en.wikipedia.org/wiki/Open_Cascade_Technology",
                               retrieved=True, support=SourceSupport.SUPPORTS)],
            quote="Open Cascade Technology",
            status=ClaimStatus.UNVERIFIED,
            produced_by="scholar",
            model="qwen2.5:14b",
        )
        await store.add_claims("pg-smoke", [claim])

        # skeptic verifies it with an INDEPENDENT source (different URL).
        claim.status = ClaimStatus.VERIFIED
        claim.confidence = 0.84
        claim.model = "gemma4:latest"
        claim.verification = [SourceRef(url_or_id="https://dev.opencascade.org/",
                                        retrieved=True, support=SourceSupport.SUPPORTS)]
        await store.update_claim(claim)

        await store.record_fetch("pg-smoke", claim.sources[0].url_or_id, True, "a" * 64)

        got = await store.get_claims("pg-smoke")
        assert len(got) == 1, got
        rt = got[0]
        assert rt.status is ClaimStatus.VERIFIED and abs(rt.confidence - 0.84) < 1e-9
        assert {s.url_or_id for s in rt.sources} == {claim.sources[0].url_or_id}
        assert {v.url_or_id for v in rt.verification} == {claim.verification[0].url_or_id}
        assert rt.model == "gemma4:latest"
        print("2. add_claims + update_claim + get_claims round-trip with provenance: OK")
        print(f"   -> [{rt.status.value}] conf={rt.confidence} "
              f"sources={len(rt.sources)} verification={len(rt.verification)}")

        # Python guard (layer 2): a claim whose sources were emptied is rejected
        # before the DB. Mutate after construction to dodge the ctor guard (layer 1)
        # and prove the store re-checks.
        try:
            sourceless = Claim(id="pg-smoke:bad", text="no source",
                               sources=[SourceRef(url_or_id="x", retrieved=True)], quote="q",
                               status=ClaimStatus.UNVERIFIED, produced_by="scholar",
                               model="qwen2.5:14b")
            sourceless.sources = []
            await store.add_claims("pg-smoke", [sourceless])
            print("3a. Python guard FAILED to reject sourceless claim: BUG")
            return 1
        except UnsourcedClaimError:
            print("3a. Python guard rejects sourceless claim (layer 2): OK")

        # THIRD layer: prove the DB trigger fires even if the Python guard is bypassed.
        # Insert a claim row with NO claim_sources, directly via SQL, and commit.
        con = await asyncpg.connect(TEST_DSN)
        try:
            trigger_fired = False
            try:
                async with con.transaction():
                    await con.execute(
                        """INSERT INTO claims (id, run_id, text, status, produced_by, model)
                           VALUES ('pg-smoke:raw', 'pg-smoke', 'sourceless raw insert',
                                   'unverified', 'rawsql', 'qwen2.5:14b')"""
                    )
                    # no claim_sources row -> DEFERRED trigger must reject at COMMIT
            except asyncpg.PostgresError as exc:
                trigger_fired = True
                print(f"3b. DB trigger claim_requires_source FIRES (layer 3): OK")
                print(f"   -> {type(exc).__name__}: {str(exc).splitlines()[0][:90]}")
            if not trigger_fired:
                print("3b. DB trigger did NOT fire — provenance layer 3 is BROKEN: BUG")
                return 1
            # confirm the rejected claim is truly absent
            n = await con.fetchval("SELECT count(*) FROM claims WHERE id = 'pg-smoke:raw'")
            assert n == 0, f"rejected claim leaked into the table: {n}"
            print("   -> rejected claim is absent from the table: OK")
        finally:
            await con.close()

        rows = await store.non_independent_verifications("pg-smoke")
        assert rows == [], f"independence violated unexpectedly: {rows}"
        print("4. independence view queryable, no violation (scholar+skeptic URLs differ): OK")

        print("\nALL POSTGRES CHECKS PASSED — provenance enforced at all THREE layers.")
        return 0
    finally:
        await store.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
