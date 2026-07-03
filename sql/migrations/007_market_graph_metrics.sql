-- Migration 007: per-market graph centrality metrics
-- psql -h localhost -p 5433 -d polymarket -f sql/migrations/007_market_graph_metrics.sql

CREATE TABLE IF NOT EXISTS market_graph_metrics (
    market_id                TEXT PRIMARY KEY,
    domain                   TEXT,
    out_degree               INTEGER,
    in_degree                INTEGER,
    eigenvector_centrality   NUMERIC(20, 10),
    betweenness_centrality   NUMERIC(20, 10),
    computed_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS market_graph_metrics_domain_idx
    ON market_graph_metrics (domain);
