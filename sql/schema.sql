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
    created_at TIMESTAMP DEFAULT NOW()
);

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
    related_market    TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS arbitrage_signals (
    id                   SERIAL PRIMARY KEY,
    parent_market        TEXT,
    related_market       TEXT,
    expected_probability NUMERIC(20, 10),
    observed_probability NUMERIC(20, 10),
    edge                 NUMERIC(20, 10),
    signal               TEXT,
    created_at           TIMESTAMP DEFAULT NOW()
);
