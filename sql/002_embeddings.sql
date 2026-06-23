-- GENESIS Fakten-Ledger — pgvector layer (semantic recall over verified claims).
--
-- This sits ON TOP of 001_ledger.sql. The ledger (001) is the source of truth and
-- already enforces "no claim without provenance" at three layers. THIS file adds the
-- ability to recall a stored claim by SEMANTIC similarity to a query — the retrieval
-- half of "no claim without source": before asserting something, find whether a
-- VERIFIED claim with provenance already covers it.
--
-- Design (honest):
--   * The embedding vector dimension is NOT hard-coded — it depends on the embedder
--     the operator injects (embeddinggemma -> 768, etc.). pgvector needs a fixed
--     dimension per column, so the dimension is substituted at schema-creation time
--     via the {dim} placeholder (PostgresLedgerStore.ensure_schema fills it in). A
--     mismatched-dimension insert is rejected by pgvector — loud, never silent.
--   * One embedding row per (claim_id, model): the SAME claim re-embedded by a
--     different embedder model is a different row, so we never silently compare
--     vectors from incompatible embedding spaces.
--   * The vector references the claim by FK with ON DELETE CASCADE: an embedding can
--     never outlive (and thus mis-attribute) its claim.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS claim_embeddings (
    claim_id      TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    embed_model   TEXT NOT NULL,          -- which embedder produced this vector
    dim           INTEGER NOT NULL,       -- declared dimension (sanity vs the column)
    embedding     vector({dim}) NOT NULL, -- the semantic vector (dimension fixed here)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (claim_id, embed_model)
);

-- Approximate-NN index (cosine). IVFFlat needs a populated table to build well, so it
-- is created lazily/optionally; an exact scan (no index) is correct, just slower, and
-- is what small test corpora use. We add it IF NOT EXISTS and tolerate few rows.
CREATE INDEX IF NOT EXISTS idx_claim_embeddings_cosine
    ON claim_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 1);
