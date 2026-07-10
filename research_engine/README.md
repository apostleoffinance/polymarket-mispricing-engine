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
  statistics.py — correlation, OLS, lead/lag, stability
        │
        ▼
  discovery.py — within-domain edges
        │
        ▼
  candidates.py (+ optional hypothesis.py)
        │
        ▼
  validation.py — promote only if stats pass
        │
        ▼
  graph.py — NetworkX + centrality
        │
        ▼
  signals.py + explanations.py
        │
        ▼
  market_relationships, candidate_relationships,
  market_graph_metrics, arbitrage_signals
```

## Edge metrics (per relationship)

| Metric | Meaning |
|--------|---------|
| `correlation` | Raw Pearson co-movement |
| `correlation_shrunk` | Sample-size adjusted correlation |
| `beta` / `conditional_slope` | OLS slope E[child \| parent] |
| `intercept` | OLS intercept |
| `strength` | Composite: \|β\| × sample weight × \|r_shrunk\| × stability |
| `lag_minutes` | Best lead/lag (positive ⇒ parent leads child) |
| `lead_correlation` | Correlation at best lag |
| `stability_score` | Rolling-window sign consistency |
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
psql -h localhost -p 5433 -d polymarket -f ../sql/migrations/010_clob_tokens_and_history_index.sql
psql -h localhost -p 5433 -d polymarket -f ../sql/migrations/011_candidate_relationships_and_edge_dynamics.sql
```

## Backtesting

Walk-forward replay (`backtest.py`):

1. Train OLS on history **strictly before** each timestamp
2. Emit virtual BUY/SELL/HOLD (same rules as live signals)
3. Measure child price at next snapshot within horizon
4. Score directional win, edge closure, simple PnL

Results in `backtest_runs` and `backtest_results`.

## Graph enrichment (candidates → validation → promote)

`run_graph.py` now:

1. Discovers within-domain edges with **lead/lag** and **stability**
2. Proposes `candidate_relationships` via token overlap (and optional LLM)
3. Statistically validates candidates (never promotes on LLM alone)
4. Attaches grounded **explanations** into `arbitrage_signals.reason_json`

Design rule: **LLM may propose; statistics may promote.**

LLM providers (OpenAI → Gemini fallback):

1. Add keys to `rust_engine/.env` (local) or GitHub Actions secrets (CI):
   - `OPENAI_API_KEY`
   - `GEMINI_API_KEY`
2. `HYPOTHESIS_LLM_ENABLED = True` in `config.py` (default).
3. Provider order: `HYPOTHESIS_LLM_PROVIDERS = ("openai", "gemini")`.

If both keys are missing, the LLM step is skipped and token-overlap candidates still run.

## Historical backfill

Fetches up to 3 years of hourly prices from the CLOB API into `probability_history`:

```bash
uv run run_backfill_history.py              # all markets in DB
uv run run_backfill_history.py --limit 100  # top 100 by volume
uv run run_backfill_history.py --years 3 --fidelity 60
```

Requires `yes_clob_token_id` on markets (populated by `cargo run` or auto-synced during backfill).
