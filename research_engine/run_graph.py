#!/usr/bin/env python3
"""Run the graph engine: discover edges, build graph, emit mispricing signals."""

from __future__ import annotations

from collections import defaultdict

from config import DOMAINS, MAX_MARKETS_PER_DOMAIN, MIN_VOLUME
from db import (
    connect,
    load_latest_prices,
    load_markets,
    load_price_history,
    load_price_matrix,
)
from discovery import discover_edges_for_domain
from graph import build_graph
from signals import (
    build_signals,
    insert_signal_if_changed,
    upsert_market_metrics,
    upsert_relationship,
)


def main() -> None:
    with connect() as conn:
        markets = load_markets(
            conn,
            DOMAINS,
            max_per_domain=MAX_MARKETS_PER_DOMAIN,
            min_volume=MIN_VOLUME,
        )
        if not markets:
            print("No markets found for configured domains.")
            return

        market_ids = [market.id for market in markets]
        history = load_price_history(conn, market_ids)
        latest = load_latest_prices(conn, market_ids)
        latest_map = latest.to_dict()

        markets_by_domain: dict[str, list] = defaultdict(list)
        for market in markets:
            markets_by_domain[market.domain].append(market)

        all_edges = []
        graphs = []
        all_metrics = []
        centrality: dict[str, float] = {}

        print("Graph Engine (quant)")
        print("=" * 40)
        print(f"Markets loaded:          {len(markets)}")
        print(f"History rows:            {len(history)}")
        print(
            f"Aligned time buckets:    "
            f"{history['recorded_at'].nunique() if not history.empty else 0}"
        )
        print()

        for domain in DOMAINS:
            domain_markets = markets_by_domain.get(domain, [])
            if not domain_markets:
                print(f"{domain}: no markets")
                continue

            domain_ids = [market.id for market in domain_markets]
            domain_history = history[history["market_id"].isin(domain_ids)]
            price_matrix = load_price_matrix(domain_history)
            edges = discover_edges_for_domain(domain_markets, price_matrix)
            graph = build_graph(domain, domain_markets, edges)
            metrics = graph.compute_centrality()

            all_edges.extend(edges)
            graphs.append(graph)
            all_metrics.extend(metrics)
            for metric in metrics:
                centrality[metric.market_id] = metric.eigenvector_centrality

            print(f"{domain}:")
            print(f"  markets: {len(domain_markets)}")
            print(f"  edges:   {len(edges)}")
            for parent_id, child_id, strength in graph.top_edges(3):
                parent_q = next(m.question for m in domain_markets if m.id == parent_id)
                child_q = next(m.question for m in domain_markets if m.id == child_id)
                print(f"    {strength:.3f}  {parent_q[:50]} -> {child_q[:50]}")

        relationships_written = 0
        for edge in all_edges:
            if upsert_relationship(conn, edge):
                relationships_written += 1

        metrics_written = upsert_market_metrics(conn, all_metrics)
        conn.commit()

        signals = build_signals(all_edges, latest_map, centrality)
        signals_inserted = 0
        for signal in signals:
            if insert_signal_if_changed(conn, signal):
                signals_inserted += 1
        conn.commit()

        total_nodes = sum(graph.node_count() for graph in graphs)
        total_edges = sum(graph.edge_count() for graph in graphs)

        print()
        print("Summary:")
        print(f"  Graph nodes:              {total_nodes}")
        print(f"  Graph edges:              {total_edges}")
        print(f"  Centrality rows upserted: {metrics_written}")
        print(f"  Relationships upserted:   {relationships_written}")
        print(f"  Signals evaluated:        {len(signals)}")
        print(f"  Signals inserted (new):   {signals_inserted}")

        actionable = [signal for signal in signals if signal.signal != "HOLD"]
        if actionable:
            print()
            print("Top actionable signals:")
            for signal in actionable[:10]:
                print(
                    f"  {signal.parent_id} -> {signal.child_id} | "
                    f"edge={signal.edge:.4f} conf={signal.confidence:.3f} "
                    f"{signal.signal}"
                )
        elif signals:
            print()
            print("All signals are HOLD (edge or confidence below thresholds).")
        else:
            print()
            print(
                "No signals yet — need more overlapping probability_history "
                "snapshots (run `cargo run` on a schedule)."
            )


if __name__ == "__main__":
    main()
