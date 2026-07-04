#!/usr/bin/env python3
"""Backfill probability_history from Polymarket CLOB API."""

from __future__ import annotations

import argparse

from backfill_history import run_backfill
from config import (
    BACKFILL_FIDELITY_MINUTES,
    BACKFILL_INCLUDE_CLOSED,
    BACKFILL_MAX_MARKETS,
    BACKFILL_REQUEST_SLEEP_SECONDS,
    BACKFILL_YEARS,
)
from db import connect


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill probability_history via CLOB prices-history"
    )
    parser.add_argument(
        "--years",
        type=int,
        default=BACKFILL_YEARS,
        help="How many years of history to request (default: 3)",
    )
    parser.add_argument(
        "--fidelity",
        type=int,
        default=BACKFILL_FIDELITY_MINUTES,
        help="Resolution in minutes (default: 60 = hourly)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max markets to backfill (default: all in DB)",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Skip closed markets",
    )
    parser.add_argument(
        "--relationships",
        action="store_true",
        help="Backfill only markets in market_relationships (thinnest first)",
    )
    args = parser.parse_args()

    max_markets = args.limit if args.limit is not None else BACKFILL_MAX_MARKETS

    print("Historical Backfill")
    print("=" * 40)
    print(f"Years:             {args.years}")
    print(f"Fidelity:          {args.fidelity} minutes")
    print(f"Include closed:    {not args.active_only}")
    print(f"Market limit:      {max_markets or 'all'}")
    print(f"Relationships:     {args.relationships}")
    print()

    with connect() as conn:
        stats = run_backfill(
            conn,
            years=args.years,
            fidelity_minutes=args.fidelity,
            max_markets=max_markets,
            include_closed=not args.active_only,
            sleep_seconds=BACKFILL_REQUEST_SLEEP_SECONDS,
            relationship_markets=args.relationships,
        )

    print()
    print("Summary:")
    print(f"  Markets processed:   {stats.markets_processed}")
    print(f"  Markets skipped:     {stats.markets_skipped}")
    print(f"  Tokens synced:       {stats.tokens_synced}")
    print(f"  Points fetched:      {stats.points_fetched}")
    print(f"  Points inserted:     {stats.points_inserted}")
    print()
    print("Next: uv run run_graph.py && uv run run_backtest.py")


if __name__ == "__main__":
    main()
