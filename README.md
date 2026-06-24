# Polymarket Mispricing Engine

A Rust-based system for ingesting Polymarket prediction market data, tracking probability snapshots over time, and building market relationship graphs toward mispricing detection.

**Current phase:** Data ingestion + probability snapshots + relationship graph (Phase 2).

---

## Project status

### Done

- [x] Rust scraper crate (`polymarket_scraper`)
- [x] Fetch active markets from the [Polymarket Gamma API](https://gamma-api.polymarket.com/markets)
- [x] Modular architecture (`models`, `parser`, `normalizer`, `database`, `http_client`, `relationships`)
- [x] `rust_decimal::Decimal` for financial fields (avoids `f64` precision issues)
- [x] Upsert market metadata into `markets`
- [x] Parse `outcomePrices` into yes/no probabilities
- [x] Time-series snapshots in `probability_history` (skips unchanged prices)
- [x] Market relationship graph in `market_relationships` (idempotent inserts)
- [x] IPv4 HTTP client with retries (fixes TLS failures on broken IPv6 routes)
- [x] Environment-based DB config via `.env` / `dotenvy`
- [x] Local PostgreSQL 17 setup (Homebrew)

### Next

- [ ] Link relationship graph to real Polymarket market IDs (not hardcoded labels)
- [ ] Mispricing detection logic
- [ ] Order book / spread data
- [ ] Scheduled / recurring scrapes
- [ ] Structured error handling with context (`anyhow`)
- [ ] Move secrets out of version control (`.env.example` + `.gitignore`)

---

## Architecture

```
Polymarket Gamma API
        │
        ▼
  http_client (IPv4 + retries)
        │
        ▼
  models / parser / normalizer
        │
        ├── upsert_market()                    → markets
        ├── insert_probability_snapshot_if_changed() → probability_history
        └── insert_relationship()              → market_relationships
                ▲
        relationships::build_relationships()
```

---

## Tech stack

| Layer | Tool |
|-------|------|
| Language | Rust (2024 edition) |
| Async runtime | Tokio |
| HTTP | reqwest (custom IPv4 DNS resolver) |
| JSON | serde / serde_json |
| Decimals | rust_decimal |
| Database | PostgreSQL 17 + sqlx |
| Config | dotenvy |

---

## Prerequisites

- [Rust](https://rustup.rs/) (stable)
- [PostgreSQL 17](https://formulae.brew.sh/formula/postgresql@17) via Homebrew

```bash
brew install postgresql@17
brew services start postgresql@17
```

Connect with:

```bash
psql -h localhost -d polymarket
```

> **Note:** If you also have EnterpriseDB PostgreSQL installed, it may grab port 5432. Use `sudo lsof -nP -iTCP:5432 -sTCP:LISTEN` to check. Your project data lives on **Homebrew PG 17** — stop EnterpriseDB if `psql` asks for a password unexpectedly.

If plain `psql` fails to connect, use `-h localhost` or set:

```bash
export PGHOST=/opt/homebrew/var/postgresql@17
```

---

## Database setup

Create the project database and tables:

```sql
CREATE DATABASE polymarket;

\c polymarket

CREATE TABLE markets (
    id         TEXT PRIMARY KEY,
    question   TEXT,
    volume     NUMERIC,
    liquidity  NUMERIC,
    active     BOOLEAN,
    closed     BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE probability_history (
    id              SERIAL PRIMARY KEY,
    market_id       TEXT NOT NULL,
    question        TEXT,
    yes_probability NUMERIC,
    no_probability  NUMERIC,
    recorded_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE market_relationships (
    id                SERIAL PRIMARY KEY,
    parent_market     TEXT NOT NULL,
    related_market    TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT NOW()
);
```

Apply deduplication constraints (run once):

```bash
psql -h localhost -d polymarket -f migrations/001_dedupe_and_constraints.sql
```

This removes duplicate relationship rows and adds a unique index on `(parent_market, related_market, relationship_type)`.

---

## Configuration

Create a `.env` file in the project root:

```env
DATABASE_URL=postgres://localhost/polymarket
```

---

## Running the scraper

From the `polymarket_scraper` directory:

```bash
cargo run
```

Expected output:

```
Connected to PostgreSQL
Will Gavin Newsom win the 2028 Democratic presidential nomination? | YES=0.207 | NO=0.793
...

Summary:
  Markets fetched: 100
  Markets upserted: 100
  Probability snapshots inserted: 4
  Probability snapshots skipped (unchanged): 96
  Relationships inserted: 0
  Relationships skipped (already exist): 10
```

On the first run, `Relationships inserted` will be **10**. On subsequent runs it will be **0** (idempotent).

---

## Verifying data

### Markets

```sql
SELECT id, question, volume, liquidity, active, closed
FROM markets
LIMIT 10;
```

### Probability history

```sql
SELECT market_id, question, yes_probability, no_probability, recorded_at
FROM probability_history
ORDER BY recorded_at DESC
LIMIT 10;
```

### Relationship graph

```sql
SELECT COUNT(*) FROM market_relationships;
-- Expected: 10

SELECT parent_market, related_market, relationship_type
FROM market_relationships
ORDER BY parent_market, related_market;

SELECT parent_market, array_agg(related_market ORDER BY related_market) AS children
FROM market_relationships
GROUP BY parent_market;
```

---

## API

The scraper calls:

```
GET https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100
```

### `markets` table

| Field | Type | Description |
|-------|------|-------------|
| `id` | text | Polymarket market ID (primary key) |
| `question` | text | Market question |
| `volume` | numeric | Total volume |
| `liquidity` | numeric | Current liquidity |
| `active` | boolean | Whether the market is active |
| `closed` | boolean | Whether the market is closed |
| `created_at` | timestamp | Row insert time (DB default) |

### `probability_history` table

| Field | Type | Description |
|-------|------|-------------|
| `market_id` | text | Polymarket market ID |
| `question` | text | Market question |
| `yes_probability` | numeric | Yes outcome price |
| `no_probability` | numeric | No outcome price |
| `recorded_at` | timestamp | Snapshot time (DB default) |

A new row is inserted only when yes/no probabilities differ from the latest snapshot for that market.

### `market_relationships` table

| Field | Type | Description |
|-------|------|-------------|
| `parent_market` | text | Parent market label |
| `related_market` | text | Related market label |
| `relationship_type` | text | e.g. `positive` |

Duplicate edges are prevented by a unique index. The graph is currently hardcoded in `src/relationships.rs`.

---

## Code quality notes

1. **Financial precision** — `volume`, `liquidity`, and probabilities use `rust_decimal::Decimal`, not `f64`.
2. **Error handling** — uses `?` for propagation instead of `.unwrap()`.
3. **Idempotency** — markets are upserted; snapshots and relationships skip duplicates.

---

## Repository structure

```
polymarket_scraper/
├── Cargo.toml
├── Cargo.lock
├── .env
├── .gitignore
├── README.md
├── migrations/
│   └── 001_dedupe_and_constraints.sql
└── src/
    ├── main.rs           # Orchestration + summary output
    ├── http_client.rs    # IPv4 DNS resolver + retries
    ├── models.rs         # Market, ProbabilitySnapshot, MarketRelationship
    ├── parser.rs         # Parse outcomePrices JSON
    ├── normalizer.rs     # Market → ProbabilitySnapshot
    ├── database.rs       # PostgreSQL upserts/inserts
    └── relationships.rs  # Hardcoded market graph
```

---

## Roadmap

1. **Phase 1 — Data ingestion** ✅
2. **Phase 2 — Enriched data + relationships** (current)
3. **Phase 3 — Mispricing engine** (fair value models, edge detection, alerts)
4. **Phase 4 — Execution** (optional: automated or semi-automated trading)
