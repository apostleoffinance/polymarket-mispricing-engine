# Polymarket Mispricing Engine

A monorepo for detecting mispriced opportunities on Polymarket prediction markets.

**Rust** ingests markets and probability snapshots. **Python** discovers relationships, validates candidates, backtests, and emits signals. **PostgreSQL** (Neon in production) is the shared contract. A **Vercel dashboard** visualizes live signals and backtests.

```text
Polymarket API
      │
      ▼
 rust_engine (hourly CI) ──► PostgreSQL ◄── research_engine (every 6h CI)
                                  │
                                  ▼
                           vercel_app dashboard
```

---

## Repository structure

```text
polymarket-mispricing-engine/
├── rust_engine/         # Ingestion: Gamma API → markets + probability_history
├── research_engine/     # Graph discovery, candidates, signals, backtests
├── vercel_app/          # Read-only research dashboard (Vercel)
├── sql/                 # Schema + migrations
├── docs/                # Architecture notes
└── .github/workflows/   # Rust ingestion + research pipeline
```

---

## Quick start

### 1. Database

Local Postgres or Neon. Apply schema + migrations:

```bash
psql "$DATABASE_URL" -f sql/schema.sql
# or apply migrations 001–011 in order (see list below)
```

### 2. Environment

```bash
cd rust_engine
cp .env.example .env
```

`rust_engine/.env` (also loaded by the research engine):

```env
DATABASE_URL=postgresql://...
OPENAI_API_KEY=...      # optional — LLM relationship hypotheses
GEMINI_API_KEY=...      # optional — fallback if OpenAI fails
```

### 3. Rust ingestion

```bash
cd rust_engine
cargo run --release
```

Fetches active markets for five domains and snapshots yes/no probabilities:

| Domain | API `tag_slug` |
|--------|----------------|
| Politics | `politics` |
| Football | `football` |
| Crypto | `crypto` |
| Macro | `macro` |
| Geopolitics | `geopolitics` |

### 4. Research engine

Requires [uv](https://docs.astral.sh/uv/):

```bash
cd research_engine
uv sync
uv run summary.py                 # DB summary
uv run run_backfill_history.py --relationships --limit 50
uv run run_graph.py               # discover + enrich + signals
uv run run_backtest.py            # walk-forward backtest
uv run run_optimize_backtest.py --quick
```

Details: [research_engine/README.md](research_engine/README.md).

### 5. Dashboard

Deploy [vercel_app/](vercel_app/) on Vercel with **Root Directory** = `vercel_app` and `DATABASE_URL` set to the same Neon URL. See [vercel_app/README.md](vercel_app/README.md).

---

## How the research graph works

```text
probability_history
        │
        ▼
 within-domain discovery (correlation, OLS, lead/lag, stability)
        │
        ▼
 candidate proposals (token overlap + optional LLM)
        │
        ▼
 statistical validation ──► promote or reject
        │
        ▼
 NetworkX graph + centrality → mispricing signals + explanations
        │
        ▼
 walk-forward backtest → dashboard
```

**Design rule:** LLMs may propose relationships; only statistics promote them into the live graph.

LLM fallback order (configurable): **OpenAI → Gemini**. If both keys are missing, token-overlap candidates still run.

---

## CI / GitHub Actions

| Workflow | Schedule | Role |
|----------|----------|------|
| [Rust Ingestion](.github/workflows/rust_ingestion.yml) | Hourly | `cargo run --release` |
| [Research Pipeline](.github/workflows/research_pipeline.yml) | Every 6h | migrate → backfill → graph → backtest |

**GitHub secrets**

| Secret | Used by |
|--------|---------|
| `DATABASE_URL` | Both pipelines + (separately) Vercel |
| `OPENAI_API_KEY` | Research graph LLM hypotheses |
| `GEMINI_API_KEY` | Research graph LLM fallback |

---

## Current status

| Phase | Status |
|-------|--------|
| Data ingestion (Gamma → Postgres) | Done |
| Probability history + CLOB backfill | Done |
| Graph discovery (correlation / OLS) | Done |
| Lead/lag + edge stability | Done |
| Candidate → validate → promote | Done |
| Optional LLM hypotheses (OpenAI → Gemini) | Done |
| Grounded signal explanations | Done |
| Walk-forward backtest + optimize | Done |
| Research + ingestion CI | Done |
| Dashboard (Vercel) | Done |
| Alerts (Discord/Slack) | Next |
| Automated trading | Later |
| Docker | Deferred |

---

## Components

| Folder | Role |
|--------|------|
| [rust_engine/](rust_engine/) | Fetch markets, store metadata & probability snapshots |
| [research_engine/](research_engine/) | Graph enrichment, signals, backtests, API |
| [vercel_app/](vercel_app/) | Live signals + backtest dashboard |
| [sql/](sql/) | Shared schema and migrations |

### Signal logic (Python)

- **Expected** child probability = `α + β · parent` (from discovered OLS edge)
- **Edge** = expected − observed child yes probability
- **Signal**: BUY / SELL / HOLD from edge + confidence thresholds in `research_engine/config.py`

---

## Migrations

```bash
psql "$DATABASE_URL" -f sql/migrations/001_dedupe_and_constraints.sql
psql "$DATABASE_URL" -f sql/migrations/002_market_ids.sql
psql "$DATABASE_URL" -f sql/migrations/003_cleanup_demo_signals.sql
psql "$DATABASE_URL" -f sql/migrations/004_market_domain.sql
psql "$DATABASE_URL" -f sql/migrations/005_relationship_strength.sql
psql "$DATABASE_URL" -f sql/migrations/006_edge_statistics.sql
psql "$DATABASE_URL" -f sql/migrations/007_market_graph_metrics.sql
psql "$DATABASE_URL" -f sql/migrations/008_signal_confidence.sql
psql "$DATABASE_URL" -f sql/migrations/009_backtest.sql
psql "$DATABASE_URL" -f sql/migrations/010_clob_tokens_and_history_index.sql
psql "$DATABASE_URL" -f sql/migrations/011_candidate_relationships_and_edge_dynamics.sql
psql "$DATABASE_URL" -f sql/migrations/012_discovery_source.sql
```

Migration `011`/`012` are also applied automatically by the research pipeline CI job.

---

## Docs

- [docs/architecture.md](docs/architecture.md) — system design
- [research_engine/README.md](research_engine/README.md) — graph / backtest details
- [rust_engine/README.md](rust_engine/README.md) — ingestion
- [vercel_app/README.md](vercel_app/README.md) — dashboard deploy

---

## License

TBD
