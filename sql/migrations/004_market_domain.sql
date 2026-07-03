-- Migration 004: tag markets by research domain (politics, football, crypto, macro, geopolitics)
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/004_market_domain.sql

ALTER TABLE markets
    ADD COLUMN IF NOT EXISTS domain TEXT;

CREATE INDEX IF NOT EXISTS markets_domain_idx ON markets (domain);
