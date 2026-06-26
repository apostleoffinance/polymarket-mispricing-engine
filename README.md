# Polymarket Mispricing Engine

A monorepo for detecting mispriced opportunities on Polymarket prediction markets.

**Rust** handles production infrastructure (scrape, store, execute). **Python** (planned) handles research (graph analysis, statistics, signal discovery). **PostgreSQL** is the shared contract between them.

---

## Repository structure

```
polymarket-mispricing-engine/
├── rust_engine/       # Rust: ingestion, DB writes, arbitrage scaffold
├── research_engine/   # Python: graph + stats (placeholder)
├── sql/               # Database schema and migrations
├── docs/              # Architecture notes
└── README.md
```

---

## Quick start

### 1. PostgreSQL

```bash
brew services start postgresql@17
psql -h localhost -p 5433 -d polymarket
```

> Homebrew PG runs on **port 5433** (EnterpriseDB may use 5432). See `docs/architecture.md`.

### 2. Database schema

```bash
psql -h localhost -p 5433 -d postgres -f sql/schema.sql
psql -h localhost -p 5433 -d polymarket -f sql/migrations/001_dedupe_and_constraints.sql
```

### 3. Rust engine

```bash
cd rust_engine
cp .env.example .env
cargo run
```

---

## Current status

| Phase | Status |
|-------|--------|
| Data ingestion (markets API → Postgres) | Done |
| Probability snapshots + relationship graph | Done |
| Arbitrage signal scaffold (BUY/SELL/HOLD) | Started (demo data) |
| Python research engine | Planned |
| Dashboard / Docker | Deferred |

See [docs/architecture.md](docs/architecture.md) for details.

---

## Components

| Folder | Role |
|--------|------|
| [rust_engine/](rust_engine/) | Fetch markets, store metadata & probabilities, build graph, compute signals |
| [research_engine/](research_engine/) | Future: pandas/NetworkX analysis on stored data |
| [sql/](sql/) | Shared schema for all services |

---

## License

TBD
