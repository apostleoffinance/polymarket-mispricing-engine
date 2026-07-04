-- Migration 010: CLOB token IDs + probability_history dedupe index
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/010_clob_tokens_and_history_index.sql

ALTER TABLE markets
    ADD COLUMN IF NOT EXISTS yes_clob_token_id TEXT,
    ADD COLUMN IF NOT EXISTS no_clob_token_id TEXT;

CREATE INDEX IF NOT EXISTS markets_yes_clob_token_idx ON markets (yes_clob_token_id);

CREATE INDEX IF NOT EXISTS probability_history_market_time_idx
    ON probability_history (market_id, recorded_at);

-- Remove exact duplicate snapshots before adding unique constraint.
DELETE FROM probability_history a
USING probability_history b
WHERE a.id > b.id
  AND a.market_id = b.market_id
  AND a.recorded_at = b.recorded_at;

CREATE UNIQUE INDEX IF NOT EXISTS probability_history_market_time_unique
    ON probability_history (market_id, recorded_at);
