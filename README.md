# Polymarket Mispricing Engine

A Rust-based system for ingesting Polymarket prediction market data and (eventually) detecting mispriced opportunities.

**Current phase:** Data ingestion — fetching active markets from the Polymarket Gamma API and persisting them to PostgreSQL.

---

## Project status

### Done

- [x] Rust scraper crate (`polymarket_scraper`)
- [x] Fetch active markets from the [Polymarket Gamma API](https://gamma-api.polymarket.com/markets)
- [x] Deserialize market JSON with `serde`
- [x] Use `rust_decimal::Decimal` for `volume` and `liquidity` (avoids `f64` precision issues)
- [x] Persist markets to PostgreSQL via `sqlx`
- [x] Idempotent inserts (`ON CONFLICT (id) DO NOTHING`)
- [x] Environment-based DB config via `.env` / `dotenvy`
- [x] Local PostgreSQL 17 setup (Homebrew)
- [x] Successfully loaded 100 active markets into the database

### Next

- [ ] Mispricing detection logic
- [ ] Outcome prices and order book data
- [ ] Scheduled / recurring scrapes (time-series snapshots)
- [ ] Structured error handling with context (`anyhow` / per-row failures)
- [ ] SQL migrations (e.g. `sqlx migrate`)
- [ ] Move secrets out of version control (`.env.example` + `.gitignore`)

---

## Architecture

```
Polymarket Gamma API
        │
        ▼
  polymarket_scraper (Rust)
   ├── reqwest        → HTTP fetch
   ├── serde          → JSON parsing
   ├── rust_decimal   → financial fields
   └── sqlx           → PostgreSQL writes
        │
        ▼
   PostgreSQL (polymarket DB)
   └── markets table
```

---

## Tech stack

| Layer | Tool |
|-------|------|
| Language | Rust (2024 edition) |
| Async runtime | Tokio |
| HTTP | reqwest |
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

If plain `psql` fails to connect, use `-h localhost` or set:

```bash
export PGHOST=/opt/homebrew/var/postgresql@17
```

---

## Database setup

Create the project database and `markets` table:

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
```

Verify:

```sql
\dt
\d markets
```

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
Stored Market 540817 - New Rihanna Album before GTA VI?
Stored Market ...
```

Verify data in psql:

```sql
SELECT id, question, volume, liquidity, active, closed
FROM markets
LIMIT 10;
```

---

## API

The scraper currently calls:

```
GET https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=100
```

Fields stored per market:

| Field | Type | Description |
|-------|------|-------------|
| `id` | text | Polymarket market ID (primary key) |
| `question` | text | Market question |
| `volume` | numeric | Total volume |
| `liquidity` | numeric | Current liquidity |
| `active` | boolean | Whether the market is active |
| `closed` | boolean | Whether the market is closed |
| `created_at` | timestamp | Row insert time (DB default) |

---

## Code quality notes

Following internal review feedback:

1. **Financial precision** — `volume` and `liquidity` use `rust_decimal::Decimal`, not `f64`, to avoid floating-point rounding errors.
2. **Error handling** — the scraper uses `?` for propagation instead of `.unwrap()`. Planned improvement: add `anyhow` for richer error context and per-row failure handling during bulk loads.

---

## Repository structure

```
polymarket_scraper/
├── Cargo.toml          # Dependencies and project metadata
├── Cargo.lock
├── .env                # Local DB connection
├── .gitignore
├── README.md
└── src/
    └── main.rs         # Scraper entry point
```

---

## Roadmap

1. **Phase 1 — Data ingestion** (current)
2. **Phase 2 — Enriched market data** (outcome prices, spreads, order book)
3. **Phase 3 — Mispricing engine** (fair value models, edge detection, alerts)
4. **Phase 4 — Execution** (optional: automated or semi-automated trading)
