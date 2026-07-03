-- Migration 006: rich edge statistics on market_relationships
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/006_edge_statistics.sql

ALTER TABLE market_relationships
    ADD COLUMN IF NOT EXISTS correlation NUMERIC(20, 10),
    ADD COLUMN IF NOT EXISTS beta NUMERIC(20, 10),
    ADD COLUMN IF NOT EXISTS conditional_slope NUMERIC(20, 10),
    ADD COLUMN IF NOT EXISTS intercept NUMERIC(20, 10),
    ADD COLUMN IF NOT EXISTS n_observations INTEGER;
