# Polymarket Mispricing Engine

A monorepo for detecting mispriced opportunities on Polymarket prediction markets.

**Rust** handles production infrastructure (scrape, store, signal generation). **Python** handles research and reporting on stored data. **PostgreSQL** is the shared contract between them.

---

## Repository structure

```
polymarket-mispricing-engine/
├── rust_engine/       # Rust: ingestion, DB writes, live arbitrage signals
├── research_engine/   # Python: DB summary and future graph/stats work
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

> Homebrew PG runs on **port 5433** (EnterpriseDB may use 5432). See [docs/architecture.md](docs/architecture.md).

### 2. Database schema

```bash
psql -h localhost -p 5433 -d postgres -f sql/schema.sql
psql -h localhost -p 5433 -d polymarket -f sql/migrations/001_dedupe_and_constraints.sql
psql -h localhost -p 5433 -d polymarket -f sql/migrations/002_market_ids.sql
psql -h localhost -p 5433 -d polymarket -f sql/migrations/003_cleanup_demo_signals.sql
```

### 3. Rust engine

```bash
cd rust_engine
cp .env.example .env
cargo run
```

Each run:

1. Fetches 100 markets from the Polymarket Gamma API
2. Upserts `markets` and snapshots `probability_history`
3. Resolves relationship templates to market IDs via keyword matching
4. Computes live arbitrage edges from scraped `outcomePrices`
5. Inserts new rows into `arbitrage_signals` only when edge/signal changes

### 4. Research engine (Python)

Requires [uv](https://docs.astral.sh/uv/):

```bash
cd research_engine
uv sync
uv run summary.py
```

Prints market counts, resolved relationships, and the latest **live** arbitrage signals (joined with market questions).

---

## Current status

| Phase | Status |
|-------|--------|
| Data ingestion (markets API → Postgres) | Done |
| Probability snapshots + relationship graph | Done |
| Live arbitrage signals (BUY/SELL/HOLD) | Done |
| Market ID resolution (`resolver.rs`) | Done |
| Signal dedup (`insert_signal_if_changed`) | Done |
| Python research summary (`uv run summary.py`) | Done |
| Relationship discovery via Python | Planned |
| Dashboard / Docker | Deferred |

See [docs/architecture.md](docs/architecture.md) for details.

---

## Components

| Folder | Role |
|--------|------|
| [rust_engine/](rust_engine/) | Fetch markets, store metadata & probabilities, resolve graph edges, compute live signals |
| [research_engine/](research_engine/) | Read stored data, print summaries; future pandas/NetworkX analysis |
| [sql/](sql/) | Shared schema and migrations for all services |

### Rust pipeline modules

| Module | Role |
|--------|------|
| `http_client.rs` | IPv4 HTTP client + retries |
| `parser.rs` / `normalizer.rs` | Parse and normalize outcome prices |
| `relationships.rs` | Relationship templates (keywords) |
| `resolver.rs` | Match templates to Polymarket market IDs |
| `arbitrage.rs` | Edge calculation → BUY / SELL / HOLD |
| `database.rs` | Upserts, snapshot dedup, signal dedup |

### Arbitrage logic

- **Expected** child probability = parent yes price × 0.65
- **Edge** = expected − observed child yes price
- **Signal**: BUY if edge > 0.10, SELL if edge < −0.10, else HOLD

---

## Configuration

`rust_engine/.env`:

```env
DATABASE_URL=postgres://localhost:5433/polymarket
```

`research_engine` loads the same URL from `rust_engine/.env`.

---

## License

TBD
