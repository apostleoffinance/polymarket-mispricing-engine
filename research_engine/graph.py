"""NetworkX market graph and centrality metrics."""

from __future__ import annotations

import networkx as nx

from models import DiscoveredEdge, MarketNode, NodeMetrics


class MarketGraph:
    """Directed weighted graph of market relationships."""

    def __init__(self, domain: str) -> None:
        self.domain = domain
        self._graph = nx.DiGraph()

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    def add_market(self, market: MarketNode) -> None:
        self._graph.add_node(
            market.id,
            question=market.question,
            domain=market.domain,
            volume=float(market.volume),
        )

    def add_edge(self, edge: DiscoveredEdge) -> None:
        self._graph.add_edge(
            edge.parent_id,
            edge.child_id,
            weight=edge.strength,
            relationship_type=edge.relationship_type,
            correlation=edge.correlation,
            correlation_shrunk=edge.correlation_shrunk,
            beta=edge.beta,
            n_observations=edge.n_observations,
            parent_label=edge.parent_label,
            child_label=edge.child_label,
            lag_minutes=edge.lag_minutes,
            lead_correlation=edge.lead_correlation,
            stability_score=edge.stability_score,
        )

    def neighbors(self, market_id: str) -> list[str]:
        if market_id not in self._graph:
            return []
        return list(self._graph.successors(market_id))

    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    def top_edges(self, limit: int = 10) -> list[tuple[str, str, float]]:
        ranked = sorted(
            self._graph.edges(data=True),
            key=lambda item: item[2].get("weight", 0.0),
            reverse=True,
        )
        return [
            (parent, child, data.get("weight", 0.0))
            for parent, child, data in ranked[:limit]
        ]

    def compute_centrality(self) -> list[NodeMetrics]:
        if self._graph.number_of_nodes() == 0:
            return []

        try:
            eigenvector = nx.eigenvector_centrality(
                self._graph, weight="weight", max_iter=500
            )
        except (nx.PowerIterationFailedConvergence, nx.NetworkXError):
            eigenvector = {node: 0.0 for node in self._graph.nodes}

        betweenness = nx.betweenness_centrality(self._graph, weight="weight")

        metrics: list[NodeMetrics] = []
        for market_id in self._graph.nodes:
            metrics.append(
                NodeMetrics(
                    market_id=market_id,
                    domain=self.domain,
                    out_degree=int(self._graph.out_degree(market_id)),
                    in_degree=int(self._graph.in_degree(market_id)),
                    eigenvector_centrality=float(eigenvector.get(market_id, 0.0)),
                    betweenness_centrality=float(betweenness.get(market_id, 0.0)),
                )
            )
        return metrics


def build_graph(domain: str, markets: list[MarketNode], edges: list[DiscoveredEdge]) -> MarketGraph:
    graph = MarketGraph(domain)
    for market in markets:
        graph.add_market(market)
    for edge in edges:
        graph.add_edge(edge)
    return graph
