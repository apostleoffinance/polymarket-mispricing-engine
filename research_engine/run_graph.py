#!/usr/bin/env python3
"""Run the graph engine: discover edges, enrich candidates, emit signals."""

from __future__ import annotations

from collections import defaultdict

from candidates import propose_token_overlap_candidates
from config import DOMAINS, MAX_MARKETS_PER_DOMAIN, MIN_VOLUME
from db import (
    connect,
    load_latest_prices,
    load_markets,
    load_price_history,
    load_price_matrix,
)
from discovery import discover_edges_for_domain
from explanations import attach_explanations
from graph import build_graph
from hypothesis import propose_llm_hypotheses
from signals import (
    build_signals,
    insert_signal_if_changed,
    upsert_market_metrics,
    upsert_relationship,
)
from validation import upsert_candidate, validate_pending_candidates


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


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
        global_matrix = load_price_matrix(history)

        markets_by_domain: dict[str, list] = defaultdict(list)
        market_by_id = {market.id: market for market in markets}
        for market in markets:
            markets_by_domain[market.domain].append(market)

        all_edges = []
        graphs = []
        all_metrics = []
        centrality: dict[str, float] = {}
        graphs_by_domain: dict[str, object] = {}

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
            graphs_by_domain[domain] = graph

            all_edges.extend(edges)
            graphs.append(graph)

            print(f"{domain}:")
            print(f"  markets: {len(domain_markets)}")
            print(f"  edges:   {len(edges)}")
            for parent_id, child_id, strength in graph.top_edges(3):
                parent_q = next(m.question for m in domain_markets if m.id == parent_id)
                child_q = next(m.question for m in domain_markets if m.id == child_id)
                print(f"    {strength:.3f}  {parent_q[:50]} -> {child_q[:50]}")

        existing_pairs = {
            _pair_key(edge.parent_id, edge.child_id) for edge in all_edges
        }

        print()
        print("Candidate enrichment")
        print("-" * 40)
        token_candidates = propose_token_overlap_candidates(
            markets,
            existing_pairs=existing_pairs,
        )
        llm_candidates = propose_llm_hypotheses(
            markets,
            existing_pairs=existing_pairs
            | {_pair_key(c.parent_id, c.child_id) for c in token_candidates},
            connected_market_ids={
                edge.parent_id for edge in all_edges
            }
            | {edge.child_id for edge in all_edges},
        )

        proposed = 0
        for candidate in token_candidates + llm_candidates:
            if upsert_candidate(conn, candidate):
                proposed += 1
        conn.commit()
        print(f"  Token candidates:      {len(token_candidates)}")
        print(f"  LLM candidates:        {len(llm_candidates)}")
        print(f"  Candidates upserted:   {proposed}")

        promoted, counts = validate_pending_candidates(
            conn,
            markets,
            global_matrix,
        )
        conn.commit()
        print(
            f"  Validated/promoted:    {counts['promoted']} "
            f"(rejected {counts['rejected']})"
        )

        known = {(edge.parent_id, edge.child_id) for edge in all_edges}
        new_promoted = 0
        for edge in promoted:
            if (edge.parent_id, edge.child_id) in known:
                continue
            all_edges.append(edge)
            known.add((edge.parent_id, edge.child_id))
            new_promoted += 1

            parent = market_by_id.get(edge.parent_id)
            child = market_by_id.get(edge.child_id)
            if parent is None or child is None:
                continue
            graph = graphs_by_domain.get(parent.domain)
            if graph is None:
                continue
            graph.add_market(parent)
            graph.add_market(child)
            graph.add_edge(edge)

        print(f"  New edges from candidates: {new_promoted}")

        for graph in graphs:
            metrics = graph.compute_centrality()
            all_metrics.extend(metrics)
            for metric in metrics:
                centrality[metric.market_id] = metric.eigenvector_centrality

        relationships_written = 0
        for edge in all_edges:
            if upsert_relationship(conn, edge):
                relationships_written += 1

        metrics_written = upsert_market_metrics(conn, all_metrics)
        conn.commit()

        signals = build_signals(all_edges, latest_map, centrality)
        signals = attach_explanations(signals, all_edges)
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
                explanation = signal.reason.get("explanation", "")
                print(
                    f"  {signal.parent_id} -> {signal.child_id} | "
                    f"edge={signal.edge:.4f} conf={signal.confidence:.3f} "
                    f"{signal.signal}"
                )
                if explanation:
                    print(f"    {explanation[:160]}")
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
