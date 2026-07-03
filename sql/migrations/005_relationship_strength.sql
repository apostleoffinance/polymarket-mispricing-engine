-- Migration 005: edge strength for discovered relationships
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/005_relationship_strength.sql

ALTER TABLE market_relationships
    ADD COLUMN IF NOT EXISTS strength NUMERIC(20, 10);
