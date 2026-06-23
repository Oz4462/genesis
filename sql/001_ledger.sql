-- GENESIS Fakten-Ledger — Phase α
-- Postgres (+ pgvector optional later). The mandatory-provenance rule from
-- CLAUDE.md §1 is enforced HERE as a database constraint, not only in code.
-- Belt and suspenders: a sourceless fact must be impossible at every layer.

CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    question      TEXT NOT NULL,
    config_hash   TEXT NOT NULL,          -- for reproducibility (A5)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every source we tried to retrieve, and whether it succeeded.
-- The gate rejects citations whose fetch was not ok (DEAD_CITATION).
CREATE TABLE IF NOT EXISTS fetches (
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    url_or_id     TEXT NOT NULL,
    ok            BOOLEAN NOT NULL,
    content_hash  TEXT,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, url_or_id)
);

CREATE TABLE IF NOT EXISTS claims (
    id            TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    text          TEXT NOT NULL,
    quote         TEXT,
    status        TEXT NOT NULL
                  CHECK (status IN ('unverified','verified','refuted','unsupported')),
    confidence    DOUBLE PRECISION NOT NULL DEFAULT 0
                  CHECK (confidence >= 0 AND confidence <= 1),
    produced_by   TEXT NOT NULL,
    model         TEXT NOT NULL,          -- enables cross-model audit (A6)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Sources backing or contradicting a claim. support: 'supports' | 'contradicts'.
-- origin: 'scholar' (original) | 'skeptic' (independent verification).
CREATE TABLE IF NOT EXISTS claim_sources (
    claim_id      TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    url_or_id     TEXT NOT NULL,
    support       TEXT NOT NULL CHECK (support IN ('supports','contradicts')),
    origin        TEXT NOT NULL CHECK (origin IN ('scholar','skeptic')),
    span          TEXT,
    PRIMARY KEY (claim_id, url_or_id, origin)
);

-- THE GUARANTEE, as a constraint: a claim must have >= 1 source row.
-- Enforced via trigger because it is a cross-row (claim<->sources) invariant.
CREATE OR REPLACE FUNCTION assert_claim_has_source() RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM claim_sources WHERE claim_id = NEW.id) THEN
        RAISE EXCEPTION
          'Claim % has no source. A fact without provenance is forbidden (CLAUDE.md §1).',
          NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- DEFERRABLE so a claim and its sources can be inserted in one transaction.
-- DROP-then-CREATE makes applying this file idempotent (CREATE CONSTRAINT TRIGGER
-- has no IF NOT EXISTS); re-running the schema must never error.
DROP TRIGGER IF EXISTS claim_requires_source ON claims;
CREATE CONSTRAINT TRIGGER claim_requires_source
    AFTER INSERT ON claims
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION assert_claim_has_source();

-- Independence rule (PHASE_ALPHA §3.4): a skeptic verification source must not
-- duplicate a scholar source for the same claim. Helper view to detect violations.
CREATE OR REPLACE VIEW v_non_independent_verifications AS
SELECT s.claim_id, s.url_or_id
FROM claim_sources s
JOIN claim_sources o
  ON s.claim_id = o.claim_id
 AND s.url_or_id = o.url_or_id
 AND s.origin = 'skeptic'
 AND o.origin = 'scholar';

CREATE INDEX IF NOT EXISTS idx_claims_run ON claims(run_id);
CREATE INDEX IF NOT EXISTS idx_claim_sources_claim ON claim_sources(claim_id);
