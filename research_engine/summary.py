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

LIVE_SIGNAL_FILTER = """
    parent_market ~ '^[0-9]+$'
    AND related_market ~ '^[0-9]+$'
"""


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

            cur.execute(
                f"SELECT COUNT(*) FROM arbitrage_signals WHERE {LIVE_SIGNAL_FILTER}"
            )
            signal_count = cur.fetchone()[0]

            print("Research Engine Summary")
            print("=" * 40)
            print(f"Markets:                 {market_count}")
            print(f"Probability snapshots:   {snapshot_count}")
            print(f"Resolved relationships:  {relationship_count}")
            print(f"Live arbitrage signals:  {signal_count}")
            print()

            cur.execute(
                """
                SELECT domain, COUNT(*)
                FROM markets
                WHERE domain IS NOT NULL
                GROUP BY domain
                ORDER BY domain
                """
            )
            domain_rows = cur.fetchall()

            if domain_rows:
                print("Markets by domain:")
                for domain, count in domain_rows:
                    print(f"  {domain}: {count}")
                print()

            cur.execute(
                f"""
                SELECT
                    s.parent_market,
                    parent_m.question,
                    s.related_market,
                    child_m.question,
                    s.edge,
                    s.signal,
                    s.created_at
                FROM arbitrage_signals s
                LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
                LEFT JOIN markets child_m ON child_m.id = s.related_market
                WHERE {LIVE_SIGNAL_FILTER}
                ORDER BY s.created_at DESC
                LIMIT 10
                """
            )
            rows = cur.fetchall()

            if not rows:
                print("No live arbitrage signals yet.")
                return

            print("Latest live signals:")
            for (
                parent_id,
                parent_question,
                child_id,
                child_question,
                edge,
                signal,
                created_at,
            ) in rows:
                parent_label = parent_question or parent_id
                child_label = child_question or child_id
                print(
                    f"  {parent_label} ({parent_id}) -> "
                    f"{child_label} ({child_id}) | "
                    f"edge={edge} {signal} @ {created_at}"
                )


if __name__ == "__main__":
    main()
