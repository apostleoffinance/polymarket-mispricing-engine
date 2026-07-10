-- Migration 012: track how each live edge was discovered (agent vs scan)
-- Applied by research pipeline CI and local setups.

ALTER TABLE market_relationships
    ADD COLUMN IF NOT EXISTS discovery_source TEXT;

UPDATE market_relationships
SET discovery_source = 'within_domain_scan'
WHERE discovery_source IS NULL;
