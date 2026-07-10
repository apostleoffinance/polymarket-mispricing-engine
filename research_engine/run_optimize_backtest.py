#!/usr/bin/env python3
"""Grid-search backtest parameters for win-rate vs signal-count tradeoff."""

from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass

from backtest import BacktestSettings, load_relationships, run_backtest
from config import (
    DOMAINS,
    OPTIMIZE_MIN_SIGNALS,
    OPTIMIZE_TARGET_WIN_RATE,
)
from db import connect, load_price_history


@dataclass(frozen=True)
class GridResult:
    edge_threshold: float
    min_confidence: float
    correlation_threshold: float
    walk_forward_only: bool
    signals: int
    wins: int
    win_rate: float


def _load_context(conn):
    edges = load_relationships(conn)
    if not edges:
        return None

    market_ids = sorted(
        {edge.parent_id for edge in edges} | {edge.child_id for edge in edges}
    )
    history = load_price_history(conn, market_ids)

    domain_by_parent: dict[str, str | None] = {}
    centrality: dict[str, float] = {}

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, domain FROM markets WHERE id = ANY(%s)",
            (market_ids,),
        )
        for market_id, domain in cur.fetchall():
            domain_by_parent[market_id] = domain

        cur.execute(
            """
            SELECT market_id, eigenvector_centrality
            FROM market_graph_metrics
            WHERE market_id = ANY(%s)
            """,
            (market_ids,),
        )
        for market_id, value in cur.fetchall():
            centrality[market_id] = float(value or 0.0)

    return edges, history, domain_by_parent, centrality


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid-search backtest parameters")
    parser.add_argument(
        "--min-signals",
        type=int,
        default=OPTIMIZE_MIN_SIGNALS,
        help="Minimum actionable signals to consider a config valid",
    )
    parser.add_argument(
        "--target-win-rate",
        type=float,
        default=OPTIMIZE_TARGET_WIN_RATE,
        help="Target directional win rate (default: 0.50)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Number of top configs to print",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Smaller grid for faster iteration",
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        choices=list(DOMAINS),
        help="Limit grid search to these parent domains",
    )
    args = parser.parse_args()

    if args.quick:
        edge_grid = (0.15, 0.20)
        confidence_grid = (0.45, 0.50)
        correlation_grid = (0.55, 0.60)
        mode_grid = (True,)
    else:
        edge_grid = (0.12, 0.15, 0.20)
        confidence_grid = (0.40, 0.45, 0.50)
        correlation_grid = (0.50, 0.55, 0.60)
        mode_grid = (True, False)

    base = BacktestSettings.from_config().with_overrides(
        domains=tuple(args.domains) if args.domains else None,
    )
    results: list[GridResult] = []

    with connect() as conn:
        context = _load_context(conn)
    if context is None:
        print("No relationships found. Run `uv run run_graph.py` first.")
        return

    edges, history, domain_by_parent, centrality = context

    total = (
        len(edge_grid)
        * len(confidence_grid)
        * len(correlation_grid)
        * len(mode_grid)
    )
    print(f"Grid search: {total} configurations")
    print(f"Min signals: {args.min_signals} | Target win rate: {args.target_win_rate:.0%}")
    print("=" * 72)

    for index, (edge, confidence, correlation, wf_only) in enumerate(
        itertools.product(edge_grid, confidence_grid, correlation_grid, mode_grid),
        start=1,
    ):
        settings = base.with_overrides(
            edge_buy_threshold=edge,
            edge_sell_threshold=-edge,
            min_signal_confidence=confidence,
            correlation_threshold=correlation,
            walk_forward_only=wf_only,
        )
        _, summary, _ = run_backtest(
            edges,
            history,
            centrality,
            domain_by_parent,
            settings,
        )
        results.append(
            GridResult(
                edge_threshold=edge,
                min_confidence=confidence,
                correlation_threshold=correlation,
                walk_forward_only=wf_only,
                signals=summary.actionable_signals,
                wins=summary.directional_wins,
                win_rate=summary.directional_win_rate,
            )
        )
        if index % 10 == 0 or index == total:
            print(f"  evaluated {index}/{total}...")

    qualifying = [r for r in results if r.signals >= args.min_signals]
    above_target = [r for r in qualifying if r.win_rate >= args.target_win_rate]

    qualifying.sort(key=lambda r: (r.win_rate, r.signals), reverse=True)
    above_target.sort(key=lambda r: (r.win_rate, r.signals), reverse=True)

    print()
    print(f"Qualifying configs (n>={args.min_signals}): {len(qualifying)}")
    print(f"Above {args.target_win_rate:.0%} win rate:          {len(above_target)}")
    print()

    def _print_table(title: str, rows: list[GridResult], limit: int) -> None:
        if not rows:
            print(f"{title}: none")
            print()
            return
        print(title)
        print("-" * 72)
        print(
            f"{'edge':>5} {'conf':>5} {'corr':>5} {'wf_only':>8} "
            f"{'signals':>8} {'win_rate':>9}"
        )
        for row in rows[:limit]:
            print(
                f"{row.edge_threshold:5.2f} {row.min_confidence:5.2f} "
                f"{row.correlation_threshold:5.2f} "
                f"{str(row.walk_forward_only):>8} "
                f"{row.signals:8d} "
                f"{row.win_rate:8.1%} ({row.wins}/{row.signals})"
            )
        print()

    if above_target:
        _print_table(
            f"Configs with win rate >= {args.target_win_rate:.0%}",
            above_target,
            args.top,
        )
    else:
        print("No configs hit target win rate. Top by win rate:")
        print()

    _print_table("Top configurations overall", qualifying, args.top)

    if qualifying:
        best = qualifying[0]
        print("Suggested config.py overrides:")
        print(f"  BACKTEST_EDGE_BUY_THRESHOLD = {best.edge_threshold}")
        print(f"  BACKTEST_EDGE_SELL_THRESHOLD = {-best.edge_threshold}")
        print(f"  BACKTEST_MIN_SIGNAL_CONFIDENCE = {best.min_confidence}")
        print(f"  BACKTEST_CORRELATION_THRESHOLD = {best.correlation_threshold}")
        print(f"  BACKTEST_WALK_FORWARD_ONLY = {best.walk_forward_only}")


if __name__ == "__main__":
    main()
