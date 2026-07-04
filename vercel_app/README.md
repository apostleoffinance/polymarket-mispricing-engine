# Polymarket Dashboard on Vercel

This folder contains a zero-cost Vercel deployment target for the dashboard.
It reads from Neon through Vercel serverless functions.

## Required Environment Variable

Set this in Vercel project settings:

```text
DATABASE_URL=your Neon PostgreSQL connection string
```

## Local Development

```bash
cd vercel_app
npm install
DATABASE_URL="postgresql://..." npm run dev
```

## Production Deploy

```bash
cd vercel_app
vercel --prod
```

Or import the repo in Vercel and set:

```text
Root Directory: vercel_app
Framework Preset: Other
Install Command: npm install
Build Command: empty
Output Directory: .
```

## Endpoints

```text
/api/health
/api/overview
/api/domains
/api/signals
/api/backtest/latest
/api/backtest/results
```

