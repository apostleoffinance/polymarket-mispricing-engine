-- Migration 008: signal confidence and explanation payload
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/008_signal_confidence.sql

ALTER TABLE arbitrage_signals
    ADD COLUMN IF NOT EXISTS confidence NUMERIC(20, 10),
    ADD COLUMN IF NOT EXISTS reason_json TEXT;
