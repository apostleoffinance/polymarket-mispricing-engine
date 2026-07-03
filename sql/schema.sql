-- Polymarket Mispricing Engine — database schema
-- Apply: psql -h localhost -p 5433 -d polymarket -f sql/schema.sql

CREATE DATABASE polymarket;

\c polymarket

CREATE TABLE IF NOT EXISTS markets (
    id         TEXT PRIMARY KEY,
    question   TEXT,
    volume     NUMERIC,
    liquidity  NUMERIC,
    active     BOOLEAN,
    closed     BOOLEAN,
    domain     TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS markets_domain_idx ON markets (domain);

CREATE TABLE IF NOT EXISTS probability_history (
    id              SERIAL PRIMARY KEY,
    market_id       TEXT NOT NULL,
    question        TEXT,
    yes_probability NUMERIC,
    no_probability  NUMERIC,
    recorded_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_relationships (
    id                SERIAL PRIMARY KEY,
    parent_market     TEXT NOT NULL,
    parent_market_id  TEXT,
    related_market    TEXT NOT NULL,
    related_market_id TEXT,
    relationship_type TEXT NOT NULL,
    strength          NUMERIC(20, 10),
    correlation       NUMERIC(20, 10),
    beta              NUMERIC(20, 10),
    conditional_slope NUMERIC(20, 10),
    intercept         NUMERIC(20, 10),
    n_observations    INTEGER,
    created_at        TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS market_relationships_unique_edge
ON market_relationships (parent_market_id, related_market_id, relationship_type);

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

CREATE TABLE IF NOT EXISTS arbitrage_signals (
    id                   SERIAL PRIMARY KEY,
    parent_market        TEXT,
    related_market       TEXT,
    expected_probability NUMERIC(20, 10),
    observed_probability NUMERIC(20, 10),
    edge                 NUMERIC(20, 10),
    signal               TEXT,
    confidence           NUMERIC(20, 10),
    reason_json          TEXT,
    created_at           TIMESTAMP DEFAULT NOW()
);
