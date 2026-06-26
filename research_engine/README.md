# Research Engine

Python layer for graph analysis, statistics, signal discovery, and backtesting.

**Status:** placeholder — not implemented yet.

## Planned scope

- Read from shared PostgreSQL tables (`markets`, `probability_history`, `market_relationships`)
- Build and analyze market relationship graphs (NetworkX / pandas)
- Discover mispricing signals and write results for `rust_engine` to act on
- Jupyter notebooks for exploratory analysis

## Setup

```bash
cd research_engine
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python summary.py
```

## Database connection

Use the same database as `rust_engine`:

```env
DATABASE_URL=postgres://localhost:5433/polymarket
```

Schema lives in `../sql/schema.sql`.
