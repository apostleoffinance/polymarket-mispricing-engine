# Research Engine

Python layer for graph analysis, statistics, signal discovery, and backtesting.

## Setup

Requires [uv](https://docs.astral.sh/uv/):

```bash
cd research_engine
uv sync
uv run summary.py
```

## Database connection

Uses the same database as `rust_engine` (loaded from `../rust_engine/.env`):

```env
DATABASE_URL=postgres://localhost:5433/polymarket
```

Schema lives in `../sql/schema.sql`.

## Planned scope

- Read from shared PostgreSQL tables (`markets`, `probability_history`, `market_relationships`)
- Build and analyze market relationship graphs (NetworkX / pandas)
- Discover mispricing signals and write results for `rust_engine` to act on
- Jupyter notebooks for exploratory analysis
