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
```
