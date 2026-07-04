#!/usr/bin/env bash
# Full research pipeline: ingest → backfill → graph → backtest → summary
#
# Usage:
#   ./scripts/run_pipeline.sh
#   ./scripts/run_pipeline.sh --skip-rust
#   ./scripts/run_pipeline.sh --backfill-limit 200
#   ./scripts/run_pipeline.sh --skip-backfill
#   ./scripts/run_pipeline.sh --all-markets   # backfill by volume, not relationships

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_RUST=0
SKIP_BACKFILL=0
BACKFILL_LIMIT=""
BACKFILL_RELATIONSHIPS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-rust)
      SKIP_RUST=1
      shift
      ;;
    --skip-backfill)
      SKIP_BACKFILL=1
      shift
      ;;
    --backfill-limit)
      BACKFILL_LIMIT="$2"
      shift 2
      ;;
    --all-markets)
      BACKFILL_RELATIONSHIPS=0
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--skip-rust] [--skip-backfill] [--backfill-limit N] [--all-markets]"
      exit 1
      ;;
  esac
done

echo "==> Polymarket research pipeline"
echo "    Root: $ROOT"
echo

if [[ "$SKIP_RUST" -eq 0 ]]; then
  echo "==> [1/5] Rust ingestion (cargo run)"
  (cd "$ROOT/rust_engine" && cargo run)
  echo
else
  echo "==> [1/5] Rust ingestion skipped"
  echo
fi

cd "$ROOT/research_engine"

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv not found. Install: https://docs.astral.sh/uv/"
  exit 1
fi

uv sync --quiet

if [[ "$SKIP_BACKFILL" -eq 0 ]]; then
  echo "==> [2/5] Historical backfill (CLOB)"
  BACKFILL_ARGS=()
  if [[ "$BACKFILL_RELATIONSHIPS" -eq 1 ]]; then
    BACKFILL_ARGS+=(--relationships)
  fi
  if [[ -n "$BACKFILL_LIMIT" ]]; then
    BACKFILL_ARGS+=(--limit "$BACKFILL_LIMIT")
  fi
  uv run run_backfill_history.py "${BACKFILL_ARGS[@]}"
  echo
else
  echo "==> [2/5] Historical backfill skipped"
  echo
fi

echo "==> [3/5] Graph engine (discovery + signals)"
uv run run_graph.py
echo

echo "==> [4/5] Backtest (walk-forward)"
uv run run_backtest.py
echo

echo "==> [5/5] Summary"
uv run summary.py
echo

echo "==> Pipeline complete"
echo "    Dashboard: cd research_engine && uv run api_server.py"
echo "    Then open http://127.0.0.1:8000"
