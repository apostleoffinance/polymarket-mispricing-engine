#!/usr/bin/env python3
"""Run walk-forward backtest and store results."""

from __future__ import annotations

import argparse

from backtest import (
    BacktestSettings,
    load_relationships,
    run_backtest,
    save_backtest_run,
    settings_to_dict,
)
from config import (
    BACKTEST_WALK_FORWARD_ONLY,
    BACKTEST_WIN_REQUIRES_PNL,
    DOMAINS,
)
from db import connect, load_price_history


def _print_summary(label: str, summary) -> None:
    print(f"  {label}")
    print(f"    Signals:    {summary.actionable_signals}")
    if summary.actionable_signals > 0:
        print(
            f"    Win rate:   {summary.directional_win_rate:.1%} "
            f"({summary.directional_wins}/{summary.actionable_signals})"
        )
        print(
            f"    Edge close: {summary.edge_closed_rate:.1%} "
            f"({summary.edge_closed_count}/{summary.actionable_signals})"
        )
    else:
        print("    Win rate:   n/a")


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


def _print_run_header(
    edges,
    domain_by_parent,
    history,
    settings: BacktestSettings,
) -> None:
    print("Backtest Engine")
    print("=" * 40)
    print(f"Relationships:       {len(edges)}")
    print(f"Markets in scope:    {len(domain_by_parent)}")
    print(f"History rows:        {len(history)}")
    print(f"Horizon:             {settings.horizon_minutes} minutes")
    print(f"Min train window:    {settings.min_train_snapshots} snapshots")
    print(f"Walk-forward only:   {settings.walk_forward_only}")
    print(f"Win requires PnL>0:  {settings.win_requires_pnl}")
    print(f"Use lag horizon:     {settings.use_lag_horizon}")
    print(f"Min stability:       {settings.min_stability}")
    print(f"Domains:             {settings.domains or 'all'}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run walk-forward backtest")
    parser.add_argument(
        "--allow-replay",
        action="store_true",
        help="Enable stored-model replay fallback (default: walk-forward only)",
    )
    parser.add_argument(
        "--legacy-win",
        action="store_true",
        help="Use legacy win rule (directional move OR fair-value cross)",
    )
    parser.add_argument(
        "--domains",
        nargs="+",
        choices=list(DOMAINS),
        help="Limit backtest to parent markets in these domains",
    )
    parser.add_argument(
        "--compare-modes",
        action="store_true",
        help="Print walk-forward-only vs replay comparison without saving",
    )
    args = parser.parse_args()

    settings = BacktestSettings.from_config().with_overrides(
        walk_forward_only=False if args.allow_replay else BACKTEST_WALK_FORWARD_ONLY,
        win_requires_pnl=False if args.legacy_win else BACKTEST_WIN_REQUIRES_PNL,
        domains=tuple(args.domains) if args.domains else None,
    )

    with connect() as conn:
        context = _load_context(conn)
    if context is None:
        print("No discovered relationships in database. Run `uv run run_graph.py` first.")
        return

    edges, history, domain_by_parent, centrality = context
    _print_run_header(edges, domain_by_parent, history, settings)

    if args.compare_modes:
        wf_settings = settings.with_overrides(walk_forward_only=True)
        full_settings = settings.with_overrides(walk_forward_only=False)

        _, wf_summary, wf_diag = run_backtest(
            edges, history, centrality, domain_by_parent, wf_settings
        )
        _, full_summary, full_diag = run_backtest(
            edges, history, centrality, domain_by_parent, full_settings
        )

        print("Mode comparison (not saved)")
        print("-" * 40)
        _print_summary("Walk-forward only", wf_summary)
        print()
        _print_summary("Walk-forward + replay", full_summary)
        print()
        _print_summary("Replay component only", full_diag.replay_summary)
        return

    outcomes, summary, diagnostics = run_backtest(
        edges,
        history,
        centrality,
        domain_by_parent,
        settings,
    )

    config = settings_to_dict(settings)
    config["diagnostics"] = {
        "pairs_evaluated": diagnostics.pairs_evaluated,
        "pairs_with_history": diagnostics.pairs_with_history,
        "pairs_walk_forward": diagnostics.pairs_walk_forward,
        "pairs_replay": diagnostics.pairs_replay,
        "walk_forward_signals": diagnostics.walk_forward_signals,
        "replay_signals": diagnostics.replay_signals,
        "pairs_agent_sourced": diagnostics.pairs_agent_sourced,
        "agent_signals": diagnostics.agent_signals,
        "pairs_skipped_stability": diagnostics.pairs_skipped_stability,
        "source_summaries": {
            source: {
                "actionable_signals": summary.actionable_signals,
                "directional_wins": summary.directional_wins,
                "directional_win_rate": summary.directional_win_rate,
            }
            for source, summary in diagnostics.source_summaries.items()
        },
    }

    with connect() as conn:
        run_id = save_backtest_run(conn, outcomes, summary, config)
        conn.commit()

    print("Diagnostics")
    print("-" * 40)
    print(f"Pairs evaluated:         {diagnostics.pairs_evaluated}")
    print(f"Pairs with history:      {diagnostics.pairs_with_history}")
    print(f"Pairs walk-forward:      {diagnostics.pairs_walk_forward}")
    print(f"Pairs replay fallback:   {diagnostics.pairs_replay}")
    print(f"Walk-forward signals:    {diagnostics.walk_forward_signals}")
    print(f"Replay signals:          {diagnostics.replay_signals}")
    print(f"Agent-sourced pairs:     {diagnostics.pairs_agent_sourced}")
    print(f"Agent-sourced signals:   {diagnostics.agent_signals}")
    print(f"Skipped (stability):     {diagnostics.pairs_skipped_stability}")
    print()
    _print_summary("Walk-forward component", diagnostics.walk_forward_summary)
    print()
    _print_summary("Replay component", diagnostics.replay_summary)
    print()

    if diagnostics.source_summaries:
        print("Win rate by discovery source")
        print("-" * 40)
        for source, source_summary in diagnostics.source_summaries.items():
            if source_summary.actionable_signals == 0:
                continue
            print(
                f"  {source}: {source_summary.directional_win_rate:.1%} "
                f"({source_summary.directional_wins}/"
                f"{source_summary.actionable_signals})"
            )
        print()

    if diagnostics.domain_summaries:
        print("Win rate by domain")
        print("-" * 40)
        for domain, domain_summary in diagnostics.domain_summaries.items():
            if domain_summary.actionable_signals == 0:
                continue
            print(
                f"  {domain}: {domain_summary.directional_win_rate:.1%} "
                f"({domain_summary.directional_wins}/"
                f"{domain_summary.actionable_signals})"
            )
        print()

    print("Results (saved)")
    print("-" * 40)
    print(f"Run id:                  {run_id}")
    _print_summary("Combined", summary)
    print(f"Mean |edge| at signal:   {summary.mean_edge_at_signal:.4f}")
    print(f"Mean |edge| after:       {summary.mean_edge_after:.4f}")
    if summary.mean_minutes_to_reprice is not None:
        print(
            f"Mean time to reprice:    "
            f"{summary.mean_minutes_to_reprice:.1f} min"
        )

    if summary.actionable_signals == 0:
        print()
        print(
            "No actionable signals. Try:\n"
            "  uv run run_optimize_backtest.py\n"
            "  uv run run_backfill_history.py --relationships"
        )
        return

    print()
    print("Sample outcomes:")
    for outcome in outcomes[:5]:
        print(
            f"  {outcome.signal_time} | {outcome.evaluation_mode} | "
            f"{outcome.parent_market_id} -> {outcome.child_market_id} | "
            f"{outcome.signal} | edge {outcome.edge_at_t:.3f} -> "
            f"{outcome.edge_at_t_plus:.3f} | win={outcome.directional_win} "
            f"pnl={outcome.simple_pnl:.3f}"
        )


if __name__ == "__main__":
    main()
