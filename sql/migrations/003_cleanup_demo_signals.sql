-- Migration 003: remove pre-live arbitrage demo rows (label-based, not market IDs)
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/003_cleanup_demo_signals.sql

DELETE FROM arbitrage_signals
WHERE parent_market !~ '^[0-9]+$'
   OR related_market !~ '^[0-9]+$';
