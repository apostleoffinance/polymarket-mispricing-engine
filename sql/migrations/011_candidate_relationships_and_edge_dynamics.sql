-- Migration 011: candidate relationships + edge dynamics (lead/lag, stability)
-- psql "$DATABASE_URL" -f sql/migrations/011_candidate_relationships_and_edge_dynamics.sql

ALTER TABLE market_relationships
    ADD COLUMN IF NOT EXISTS lag_minutes INTEGER,
    ADD COLUMN IF NOT EXISTS lead_correlation NUMERIC(20, 10),
    ADD COLUMN IF NOT EXISTS stability_score NUMERIC(20, 10);

CREATE TABLE IF NOT EXISTS candidate_relationships (
    id                   SERIAL PRIMARY KEY,
    parent_market_id     TEXT NOT NULL,
    child_market_id      TEXT NOT NULL,
    parent_question      TEXT,
    child_question       TEXT,
    parent_domain        TEXT,
    child_domain         TEXT,
    source               TEXT NOT NULL,
    rationale            TEXT,
    status               TEXT NOT NULL DEFAULT 'proposed',
    confidence           NUMERIC(20, 10),
    correlation          NUMERIC(20, 10),
    correlation_shrunk   NUMERIC(20, 10),
    beta                 NUMERIC(20, 10),
    intercept            NUMERIC(20, 10),
    lag_minutes          INTEGER,
    lead_correlation     NUMERIC(20, 10),
    stability_score      NUMERIC(20, 10),
    n_observations       INTEGER,
    strength             NUMERIC(20, 10),
    rejection_reason     TEXT,
    created_at           TIMESTAMP DEFAULT NOW(),
    updated_at           TIMESTAMP DEFAULT NOW(),
    CONSTRAINT candidate_relationships_status_check
        CHECK (status IN ('proposed', 'validated', 'rejected', 'promoted')),
    CONSTRAINT candidate_relationships_pair_source_unique
        UNIQUE (parent_market_id, child_market_id, source)
);

CREATE INDEX IF NOT EXISTS candidate_relationships_status_idx
    ON candidate_relationships (status);

CREATE INDEX IF NOT EXISTS candidate_relationships_domains_idx
    ON candidate_relationships (parent_domain, child_domain);
