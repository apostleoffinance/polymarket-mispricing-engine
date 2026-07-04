#!/usr/bin/env python3
"""Read stored market data and print a research summary."""

from __future__ import annotations

from db import connect

LIVE_SIGNAL_FILTER = """
    parent_market ~ '^[0-9]+$'
    AND related_market ~ '^[0-9]+$'
"""


def main() -> None:
    with connect() as conn:
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

            cur.execute(
                """
                SELECT COUNT(*)
                FROM markets
                WHERE yes_clob_token_id IS NOT NULL
                """
            )
            token_count = cur.fetchone()[0]

            print("Research Engine Summary")
            print("=" * 40)
            print(f"Markets:                 {market_count}")
            print(f"Markets with CLOB token: {token_count}")
            print(f"Probability snapshots:   {snapshot_count}")
            print(f"Resolved relationships:  {relationship_count}")
            print(f"Live arbitrage signals:  {signal_count}")
            print()

            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE n >= 100) AS markets_100_plus,
                    COUNT(*) FILTER (WHERE n >= 500) AS markets_500_plus,
                    ROUND(AVG(n), 1) AS avg_snapshots,
                    MAX(n) AS max_snapshots
                FROM (
                    SELECT market_id, COUNT(*) AS n
                    FROM probability_history
                    GROUP BY market_id
                ) counts
                """
            )
            hist_stats = cur.fetchone()
            if hist_stats:
                print("History depth:")
                print(f"  Markets with 100+ snapshots: {hist_stats[0]}")
                print(f"  Markets with 500+ snapshots: {hist_stats[1]}")
                print(f"  Avg snapshots / market:    {hist_stats[2]}")
                print(f"  Max snapshots / market:    {hist_stats[3]}")
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
                """
                SELECT
                    id,
                    started_at,
                    actionable_signals,
                    directional_wins,
                    directional_win_rate,
                    edge_closed_rate,
                    mean_edge_at_signal,
                    mean_edge_after,
                    mean_minutes_to_reprice
                FROM backtest_runs
                ORDER BY id DESC
                LIMIT 1
                """
            )
            backtest = cur.fetchone()
            if backtest:
                (
                    run_id,
                    started_at,
                    actionable,
                    directional_wins,
                    win_rate,
                    edge_closed_rate,
                    mean_edge_at,
                    mean_edge_after,
                    mean_reprice,
                ) = backtest
                print("Latest backtest:")
                print(f"  Run id:                {run_id}")
                print(f"  Started:               {started_at}")
                print(f"  Actionable signals:    {actionable}")
                if actionable and actionable > 0:
                    wins = directional_wins or 0
                    closed = edge_closed_rate
                    print(
                        f"  Directional win rate:  "
                        f"{float(win_rate or 0):.1%} ({wins}/{actionable})"
                    )
                    print(
                        f"  Edge closed rate:      "
                        f"{float(closed or 0):.1%}"
                    )
                else:
                    print(f"  Directional win rate:  n/a")
                    print(f"  Edge closed rate:      n/a")
                print(f"  Mean |edge| at signal: {float(mean_edge_at or 0):.4f}")
                print(f"  Mean |edge| after:     {float(mean_edge_after or 0):.4f}")
                if mean_reprice is not None:
                    print(f"  Mean time to reprice:  {float(mean_reprice):.1f} min")
                print()

            cur.execute(
                f"""
                SELECT
                    s.parent_market,
                    parent_m.question,
                    s.related_market,
                    child_m.question,
                    s.edge,
                    s.confidence,
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
                confidence,
                signal,
                created_at,
            ) in rows:
                parent_label = parent_question or parent_id
                child_label = child_question or child_id
                conf = f" conf={float(confidence):.3f}" if confidence is not None else ""
                print(
                    f"  {parent_label} ({parent_id}) -> "
                    f"{child_label} ({child_id}) | "
                    f"edge={edge} {signal}{conf} @ {created_at}"
                )


if __name__ == "__main__":
    main()
