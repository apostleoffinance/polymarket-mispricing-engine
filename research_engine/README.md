# Research Engine

Python graph engine for relationship discovery and mispricing signals.

## Setup

```bash
cd research_engine
uv sync
```

## Commands

```bash
uv run summary.py      # read-only DB summary
uv run run_graph.py    # quant graph: discovery + centrality + signals
uv run run_backtest.py # walk-forward backtest + store results
uv run run_backfill_history.py --limit 50  # CLOB history backfill
```

## Pipeline

```text
probability_history
        │
        ▼
  statistics.py — correlation (shrunk), OLS beta, composite strength
        │
        ▼
  discovery.py — edges per domain
        │
        ▼
  graph.py — NetworkX + eigenvector/betweenness centrality
        │
        ▼
  signals.py — E[child|parent] = α + β·parent, confidence, reason_json
        │
        ▼
  market_relationships, market_graph_metrics, arbitrage_signals
```

## Edge metrics (per relationship)

| Metric | Meaning |
|--------|---------|
| `correlation` | Raw Pearson co-movement |
| `correlation_shrunk` | Sample-size adjusted correlation |
| `beta` / `conditional_slope` | OLS slope E[child \| parent] |
| `intercept` | OLS intercept |
| `strength` | Composite: \|β\| × sample weight × \|r_shrunk\| |
| `n_observations` | Aligned history points |

## Node metrics (`market_graph_metrics`)

- `out_degree`, `in_degree`
- `eigenvector_centrality`
- `betweenness_centrality`

## Configuration

Edit `config.py` — key thresholds:

- `MIN_OVERLAPPING_SNAPSHOTS` (default 10)
- `CORRELATION_THRESHOLD` (0.5)
- `MIN_SIGNAL_CONFIDENCE` (0.35)

## Migrations

```bash
psql -h localhost -p 5433 -d polymarket -f ../sql/migrations/006_edge_statistics.sql
psql -h localhost -p 5433 -d polymarket -f ../sql/migrations/007_market_graph_metrics.sql
psql -h localhost -p 5433 -d polymarket -f ../sql/migrations/008_signal_confidence.sql
psql -h localhost -p 5433 -d polymarket -f ../sql/migrations/009_backtest.sql
```

## Backtesting

Walk-forward replay (`backtest.py`):

1. Train OLS on history **strictly before** each timestamp
2. Emit virtual BUY/SELL/HOLD (same rules as live signals)
3. Measure child price at next snapshot within horizon
4. Score directional win, edge closure, simple PnL

Results in `backtest_runs` and `backtest_results`.

## Historical backfill

Fetches up to 3 years of hourly prices from the CLOB API into `probability_history`:

```bash
psql -h localhost -p 5433 -d polymarket -f ../sql/migrations/010_clob_tokens_and_history_index.sql
uv run run_backfill_history.py              # all markets in DB
uv run run_backfill_history.py --limit 100  # top 100 by volume
uv run run_backfill_history.py --years 3 --fidelity 60
```

Requires `yes_clob_token_id` on markets (populated by `cargo run` or auto-synced during backfill).
