"""Discover market relationships from aligned price history."""

from __future__ import annotations

import pandas as pd

from config import (
    CORRELATION_THRESHOLD,
    MAX_EDGES_PER_DOMAIN,
    MIN_STRENGTH,
)
from models import DiscoveredEdge, MarketNode
from statistics import compute_pair_statistics


def discover_edges_for_domain(
    markets: list[MarketNode],
    price_matrix: pd.DataFrame,
) -> list[DiscoveredEdge]:
    """Find statistically supported pairs within a domain."""
    if price_matrix.shape[1] < 2:
        return []

    market_by_id = {market.id: market for market in markets}
    market_ids = [mid for mid in price_matrix.columns if mid in market_by_id]
    if len(market_ids) < 2:
        return []

    edges: list[DiscoveredEdge] = []

    for i, market_a_id in enumerate(market_ids):
        for market_b_id in market_ids[i + 1 :]:
            stats = compute_pair_statistics(
                price_matrix[market_a_id],
                price_matrix[market_b_id],
            )
            if stats is None:
                continue
            if abs(stats.correlation_shrunk) < CORRELATION_THRESHOLD:
                continue
            if stats.strength < MIN_STRENGTH:
                continue

            parent_market, child_market = _orient_parent_child(
                market_by_id[market_a_id],
                market_by_id[market_b_id],
            )

            parent_series = price_matrix[parent_market.id]
            child_series = price_matrix[child_market.id]
            oriented_stats = compute_pair_statistics(parent_series, child_series)
            if oriented_stats is None:
                continue

            rel_type = (
                "discovered_positive"
                if oriented_stats.beta >= 0
                else "discovered_negative"
            )

            edges.append(
                DiscoveredEdge(
                    parent_id=parent_market.id,
                    parent_label=_short_label(parent_market.question),
                    child_id=child_market.id,
                    child_label=_short_label(child_market.question),
                    relationship_type=rel_type,
                    strength=oriented_stats.strength,
                    correlation=oriented_stats.correlation,
                    correlation_shrunk=oriented_stats.correlation_shrunk,
                    beta=oriented_stats.beta,
                    intercept=oriented_stats.intercept,
                    conditional_slope=oriented_stats.conditional_slope,
                    n_observations=oriented_stats.n_observations,
                )
            )

    edges.sort(key=lambda edge: edge.strength, reverse=True)
    return edges[:MAX_EDGES_PER_DOMAIN]


def _orient_parent_child(
    market_a: MarketNode,
    market_b: MarketNode,
) -> tuple[MarketNode, MarketNode]:
    """Parent = higher volume (liquidity tie-breaker)."""
    if market_a.volume != market_b.volume:
        return (
            (market_a, market_b)
            if market_a.volume >= market_b.volume
            else (market_b, market_a)
        )
    if market_a.liquidity != market_b.liquidity:
        return (
            (market_a, market_b)
            if market_a.liquidity >= market_b.liquidity
            else (market_b, market_a)
        )
    return market_a, market_b


def _short_label(question: str, max_len: int = 80) -> str:
    question = question.strip()
    if len(question) <= max_len:
        return question
    return question[: max_len - 3] + "..."
