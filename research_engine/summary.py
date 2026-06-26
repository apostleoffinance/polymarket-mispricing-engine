#!/usr/bin/env python3
"""Read stored market data and print a research summary."""

import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / "rust_engine" / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgres://localhost:5433/polymarket"
)


def main() -> None:
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM markets")
            market_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM probability_history")
            snapshot_count = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*) FROM market_relationships
                WHERE parent_market_id IS NOT NULL
                  AND related_market_id IS NOT NULL
                """
            )
            relationship_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM arbitrage_signals")
            signal_count = cur.fetchone()[0]

            print("Research Engine Summary")
            print("=" * 40)
            print(f"Markets:                 {market_count}")
            print(f"Probability snapshots:   {snapshot_count}")
            print(f"Resolved relationships:  {relationship_count}")
            print(f"Arbitrage signals:       {signal_count}")
            print()

            cur.execute(
                """
                SELECT parent_market, related_market, edge, signal, created_at
                FROM arbitrage_signals
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
            rows = cur.fetchall()

            if not rows:
                print("No arbitrage signals yet.")
                return

            print("Latest signals:")
            for parent_id, child_id, edge, signal, created_at in rows:
                print(
                    f"  {parent_id} -> {child_id} | edge={edge} {signal} @ {created_at}"
                )


if __name__ == "__main__":
    main()
