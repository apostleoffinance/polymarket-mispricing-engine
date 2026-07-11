# Architecture

## Overview

The mispricing engine is a monorepo with a clear split between **production infrastructure** (Rust) and **research** (Python), connected by PostgreSQL.

```
polymarket-mispricing-engine/
├── rust_engine/       # Scrape, store, execute, risk (production paths)
├── research_engine/   # Graph analysis, statistics, signal discovery
├── sql/               # Shared database schema and migrations
└── docs/              # Architecture and notes
```

## Data flow

```
Polymarket Gamma API
        │
        ▼
  rust_engine (fetch + normalize)
        │
        ▼
   PostgreSQL  ◄──── research_engine (read + analyze)
        │
        ▼
  rust_engine (execute signals — future)
```

## Component responsibilities

| Component | Language | Responsibility |
|-----------|----------|----------------|
| `rust_engine` | Rust | API ingestion, DB writes, IPv4 HTTP client, arbitrage execution scaffold |
| `research_engine` | Python | Correlation, graph stats, backtests, notebooks (planned) |
| `sql/` | SQL | Schema source of truth shared by Rust and Python |
| `dashboard/` | Vercel (`vercel_app/`) | Live signals + backtest visualization |

## Database tables

| Table | Written by | Purpose |
|-------|------------|---------|
| `markets` | rust_engine | Market metadata |
| `probability_history` | rust_engine | Time-series yes/no prices |
| `market_relationships` | rust_engine | Parent → related market edges |
| `arbitrage_signals` | rust_engine | Expected vs observed edge + BUY/SELL/HOLD |

## Design principles

1. **PostgreSQL is the contract** — Rust and Python communicate through the DB, not direct calls.
2. **Financial precision** — use `Decimal` / `NUMERIC`, never `f64` for money or probabilities.
3. **Idempotent writes** — upserts, skip unchanged snapshots, deduplicated relationships.
4. **Incremental growth** — add `dashboard/` and `docker-compose.yml` when multiple services need to run together.

## Current phase

- Phase 1 (ingestion): done
- Phase 2 (snapshots + graph): done
- Phase 3 (mispricing): in progress — live probabilities, market ID resolution, signal dedup

## Roadmap

1. ~~Wire arbitrage to live probabilities from scraped markets~~
2. ~~Link graph labels to Polymarket market IDs~~
3. ~~Bootstrap `research_engine` Python summary script~~
4. ~~Expand relationship templates / discovery via Python~~ (correlation discovery done)
5. ~~Dashboard~~ — deployed via `vercel_app/` on Vercel
6. Docker when operational needs arise
