-- Run once: psql -h localhost -p 5433 -d polymarket -f sql/migrations/001_dedupe_and_constraints.sql

-- Remove duplicate relationship edges (keep oldest row per edge).
DELETE FROM market_relationships a
USING market_relationships b
WHERE a.id > b.id
  AND a.parent_market = b.parent_market
  AND a.related_market = b.related_market
  AND COALESCE(a.relationship_type, '') = COALESCE(b.relationship_type, '');

CREATE UNIQUE INDEX IF NOT EXISTS market_relationships_unique_edge
ON market_relationships (parent_market, related_market, relationship_type);

-- Optional: remove back-to-back identical probability snapshots.
DELETE FROM probability_history a
USING probability_history b
WHERE a.market_id = b.market_id
  AND a.id > b.id
  AND a.yes_probability = b.yes_probability
  AND a.no_probability = b.no_probability
  AND a.recorded_at = b.recorded_at;
