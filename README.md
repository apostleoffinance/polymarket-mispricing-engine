# Polymarket Mispricing Engine

A monorepo for detecting mispriced opportunities on Polymarket prediction markets.

**Rust** handles ingestion (scrape, store). **Python** discovers graph edges and mispricing signals. **PostgreSQL** is the shared contract between them.

---

## Repository structure

```
polymarket-mispricing-engine/
├── rust_engine/       # Rust: domain-scoped ingestion + snapshots
├── research_engine/   # Python: graph engine + mispricing signals
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
psql -h localhost -p 5433 -d polymarket -f sql/migrations/004_market_domain.sql
psql -h localhost -p 5433 -d polymarket -f sql/migrations/005_relationship_strength.sql
psql -h localhost -p 5433 -d polymarket -f sql/migrations/006_edge_statistics.sql
psql -h localhost -p 5433 -d polymarket -f sql/migrations/007_market_graph_metrics.sql
psql -h localhost -p 5433 -d polymarket -f sql/migrations/008_signal_confidence.sql
```

### 3. Rust engine

```bash
cd rust_engine
cp .env.example .env
cargo run
```

Each run fetches markets from five Polymarket event tags only:

| Domain | API `tag_slug` |
|--------|----------------|
| Politics | `politics` |
| Football | `football` |
| Crypto | `crypto` |
| Macro | `macro` |
| Geopolitics | `geopolitics` |

Pipeline:

1. Fetches active markets from those tagged events (paginated)
2. Upserts `markets` (with `domain`) and snapshots `probability_history`

Then run the Python graph engine (`uv run run_graph.py`) to discover relationships and signals.

### 4. Research engine (Python)

Requires [uv](https://docs.astral.sh/uv/):

```bash
cd research_engine
uv sync
uv run summary.py          # read-only summary
uv run run_graph.py        # discover edges + mispricing signals
```

Python discovers correlated market relationships and writes `market_relationships` + `arbitrage_signals`. Rust handles ingestion only.

---

## Current status

| Phase | Status |
|-------|--------|
| Data ingestion (markets API → Postgres) | Done |
| Probability snapshots + relationship graph | Done |
| Live arbitrage signals (BUY/SELL/HOLD) | Done (Python `run_graph.py`) |
| Graph engine (NetworkX + correlation) | Done |
| Market ID resolution (`resolver.rs`) | Done (Rust, legacy templates) |
| Signal dedup | Done |
| Python research summary (`uv run summary.py`) | Done |
| Relationship discovery via Python | Done (correlation) |
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
