# Rust Engine

Production infrastructure for Polymarket data ingestion, storage, and signal execution.

Part of the [polymarket-mispricing-engine](../) monorepo.

## Run

```bash
cp .env.example .env
cargo run
```

## Modules

| File | Role |
|------|------|
| `main.rs` | Pipeline orchestration |
| `http_client.rs` | IPv4 HTTP client + retries |
| `models.rs` | Data structures |
| `parser.rs` | Parse outcome prices |
| `normalizer.rs` | Market → probability snapshot |
| `database.rs` | PostgreSQL writes |
| `relationships.rs` | Market relationship graph |
| `arbitrage.rs` | Edge calculation + BUY/SELL/HOLD |

## Configuration

```env
DATABASE_URL=postgres://localhost:5433/polymarket
```

Database schema: [`../sql/schema.sql`](../sql/schema.sql)

## Docs

- [Monorepo README](../README.md)
- [Architecture](../docs/architecture.md)
