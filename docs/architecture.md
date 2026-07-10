# Architecture

## Overview

The mispricing engine is a monorepo with a clear split between **ingestion** (Rust), **research** (Python), and **visualization** (Vercel), connected by PostgreSQL.

```text
polymarket-mispricing-engine/
├── rust_engine/       # Scrape + store markets / probabilities
├── research_engine/   # Graph analysis, candidates, signals, backtests
├── vercel_app/        # Read-only dashboard
├── sql/               # Shared database schema and migrations
└── docs/              # Architecture and notes
```

## Data flow

```text
Polymarket Gamma / CLOB APIs
            │
            ▼
      rust_engine (ingest)
            │
            ▼
       PostgreSQL
            │
     ┌──────┴──────┐
     ▼             ▼
research_engine   vercel_app
 (analyze)        (dashboard)
     │
     ▼
execute trades — future
```

## Component responsibilities

| Component | Language | Responsibility |
|-----------|----------|----------------|
| `rust_engine` | Rust | API ingestion, DB writes, IPv4 HTTP client |
| `research_engine` | Python | Discovery, lead/lag, candidates, LLM hypotheses, signals, backtests |
| `vercel_app` | JS | Live signals + backtest visualization |
| `sql/` | SQL | Schema source of truth |

## Database tables

| Table | Written by | Purpose |
|-------|------------|---------|
| `markets` | rust_engine | Market metadata |
| `probability_history` | rust_engine (+ backfill) | Time-series yes/no prices |
| `market_relationships` | research_engine | Promoted edges (stats + lag/stability) |
| `candidate_relationships` | research_engine | Proposed edges awaiting validation |
| `market_graph_metrics` | research_engine | Centrality metrics |
| `arbitrage_signals` | research_engine | Expected vs observed edge + BUY/SELL/HOLD |
| `backtest_runs` / `backtest_results` | research_engine | Walk-forward evaluation |

## Design principles

1. **PostgreSQL is the contract** — services communicate through the DB, not direct calls.
2. **Financial precision** — use `Decimal` / `NUMERIC`, never `f64` for money or probabilities.
3. **Idempotent writes** — upserts, skip unchanged snapshots, deduplicated relationships.
4. **LLM proposes, statistics promote** — agents never write the live graph directly.
5. **Incremental growth** — alerts and execution come after research quality is proven.

## Current phase

- Phase 1 (ingestion): done
- Phase 2 (snapshots + graph): done
- Phase 3 (mispricing + enrichment): done for research path
- Phase 4 (alerts): next
- Phase 5 (execution): later

## Roadmap

1. ~~Wire live probabilities from scraped markets~~
2. ~~Python relationship discovery + signals~~
3. ~~Walk-forward backtest + CI~~
4. ~~Dashboard (`vercel_app/`)~~
5. ~~Graph enrichment: lead/lag, stability, candidate→validate→promote~~
6. ~~Optional LLM hypotheses with OpenAI → Gemini fallback~~
7. Alerts (Discord/Slack) on high-confidence new signals
8. Paper trading / execution (future)
9. Docker when operational needs arise
