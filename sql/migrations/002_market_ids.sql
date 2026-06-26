-- Migration 002: link relationships to market IDs
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/002_market_ids.sql

ALTER TABLE market_relationships
    ADD COLUMN IF NOT EXISTS parent_market_id TEXT,
    ADD COLUMN IF NOT EXISTS related_market_id TEXT;

-- Remove label-only rows from earlier runs (re-inserted with IDs on next cargo run).
DELETE FROM market_relationships
WHERE parent_market_id IS NULL OR related_market_id IS NULL;

DROP INDEX IF EXISTS market_relationships_unique_edge;

CREATE UNIQUE INDEX IF NOT EXISTS market_relationships_unique_edge
ON market_relationships (parent_market_id, related_market_id, relationship_type);
