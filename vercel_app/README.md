# Polymarket Dashboard on Vercel

Read-only dashboard for live signals, domain win rates, and the latest backtest.
Connects to the same Neon PostgreSQL database used by the Rust ingestion and research pipelines.

## What you see

- **Overview** — markets, snapshots, relationships, signals, candidate counts, lag/stability
- **Domain cards** — backtest win rate and live signal count per category
- **Latest backtest** — actionable signals, wins, edge closure, reprice time
- **Research alerts** — low sample, enrichment status, stale backtest
- **Live signals** — edge + grounded explanation + lead/lag + stability
- **Candidates** — proposed / promoted / rejected relationships (token + LLM)
- **Backtest results** — latest walk-forward outcomes

## Deploy (recommended: Vercel UI)

1. Go to [vercel.com/new](https://vercel.com/new) and import `apostleoffinance/polymarket-mispricing-engine`.
2. Set **Root Directory** to `vercel_app`.
3. Framework preset: **Other** (no build command needed).
4. Add environment variable:
   ```text
   DATABASE_URL=<your Neon connection string>
   ```
   Use the same value as the `DATABASE_URL` GitHub secret for your pipelines.
5. Deploy.

Your dashboard will be live at `https://<project>.vercel.app`.

## Deploy (recommended: Vercel Git integration)

Import the repo on [Vercel](https://vercel.com/new) with **Root Directory** = `vercel_app`.
Vercel redeploys automatically on pushes to `main`. No GitHub Actions deploy workflow is required.

## Local development

```bash
cd vercel_app
cp .env.example .env
# Edit .env with your DATABASE_URL
npm install
npm run dev
```

Open `http://localhost:3000`.

## API endpoints

```text
GET /api/health
GET /api/overview
GET /api/overview?domain=politics
GET /api/domains
GET /api/signals?limit=20
GET /api/signals?limit=20&domain=crypto
GET /api/candidates?limit=30
GET /api/candidates?status=promoted
GET /api/backtest/latest
GET /api/backtest/latest?domain=politics
GET /api/backtest/results?limit=50
```

Signal payloads include `explanation`, `lag_minutes`, `lead_correlation`, and `stability_score` when available.

## Research baseline (Phase A)

Use the dashboard alerts to judge whether signals are research-ready:

| Signal | Meaning |
|--------|---------|
| n < 30 actionable backtest signals | Win rate not statistically meaningful |
| Win rate < 50% with n ≥ 30 | Tune thresholds (`run_optimize_backtest.py`) before alerts |
| Backtest > 12h old | Research pipeline may have failed or not run |
| Snapshots < 10k | Need more ingestion / backfill |

Next step after baseline review: run `uv run run_optimize_backtest.py --quick` in `research_engine/`.
