"""Mispricing signals from graph edges."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

from psycopg2.extensions import connection as PgConnection

from config import EDGE_BUY_THRESHOLD, EDGE_SELL_THRESHOLD, MIN_SIGNAL_CONFIDENCE
from models import DiscoveredEdge
from statistics import expected_from_regression


@dataclass(frozen=True)
class MispricingSignal:
    parent_id: str
    child_id: str
    expected_probability: float
    observed_probability: float
    edge: float
    signal: str
    confidence: float
    reason: dict[str, float | int | str]


def compute_confidence(
    edge: DiscoveredEdge,
    parent_centrality: float,
) -> float:
    sample_factor = min(1.0, edge.n_observations / 50.0)
    centrality_factor = 0.5 + (0.5 * min(1.0, parent_centrality))
    return min(1.0, edge.strength * sample_factor * centrality_factor)


def determine_signal(edge_value: float, confidence: float) -> str:
    if confidence < MIN_SIGNAL_CONFIDENCE:
        return "HOLD"
    if edge_value > EDGE_BUY_THRESHOLD:
        return "BUY"
    if edge_value < EDGE_SELL_THRESHOLD:
        return "SELL"
    return "HOLD"


def build_signals(
    edges: list[DiscoveredEdge],
    latest_prices: dict[str, float],
    centrality: dict[str, float],
) -> list[MispricingSignal]:
    signals: list[MispricingSignal] = []

    for edge in edges:
        parent_yes = latest_prices.get(edge.parent_id)
        child_yes = latest_prices.get(edge.child_id)
        if parent_yes is None or child_yes is None:
            continue

        expected = expected_from_regression(parent_yes, edge.intercept, edge.beta)
        mispricing_edge = expected - child_yes
        parent_centrality = centrality.get(edge.parent_id, 0.0)
        confidence = compute_confidence(edge, parent_centrality)
        signal = determine_signal(mispricing_edge, confidence)

        reason = {
            "relationship_type": edge.relationship_type,
            "strength": round(edge.strength, 4),
            "correlation": round(edge.correlation, 4),
            "correlation_shrunk": round(edge.correlation_shrunk, 4),
            "beta": round(edge.beta, 4),
            "conditional_slope": round(edge.conditional_slope, 4),
            "n_observations": edge.n_observations,
            "parent_centrality": round(parent_centrality, 4),
            "edge": round(mispricing_edge, 4),
            "signal": signal,
            "lag_minutes": edge.lag_minutes,
            "lead_correlation": round(edge.lead_correlation, 4),
            "stability_score": round(edge.stability_score, 4),
        }

        signals.append(
            MispricingSignal(
                parent_id=edge.parent_id,
                child_id=edge.child_id,
                expected_probability=expected,
                observed_probability=child_yes,
                edge=mispricing_edge,
                signal=signal,
                confidence=confidence,
                reason=reason,
            )
        )

    signals.sort(key=lambda item: abs(item.edge), reverse=True)
    return signals


def upsert_relationship(conn: PgConnection, edge: DiscoveredEdge) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO market_relationships (
                parent_market,
                parent_market_id,
                related_market,
                related_market_id,
                relationship_type,
                strength,
                correlation,
                beta,
                conditional_slope,
                intercept,
                n_observations,
                lag_minutes,
                lead_correlation,
                stability_score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (parent_market_id, related_market_id, relationship_type)
            DO UPDATE SET
                parent_market = EXCLUDED.parent_market,
                related_market = EXCLUDED.related_market,
                strength = EXCLUDED.strength,
                correlation = EXCLUDED.correlation,
                beta = EXCLUDED.beta,
                conditional_slope = EXCLUDED.conditional_slope,
                intercept = EXCLUDED.intercept,
                n_observations = EXCLUDED.n_observations,
                lag_minutes = EXCLUDED.lag_minutes,
                lead_correlation = EXCLUDED.lead_correlation,
                stability_score = EXCLUDED.stability_score
            """,
            (
                edge.parent_label,
                edge.parent_id,
                edge.child_label,
                edge.child_id,
                edge.relationship_type,
                Decimal(str(edge.strength)),
                Decimal(str(edge.correlation)),
                Decimal(str(edge.beta)),
                Decimal(str(edge.conditional_slope)),
                Decimal(str(edge.intercept)),
                edge.n_observations,
                edge.lag_minutes,
                Decimal(str(edge.lead_correlation)),
                Decimal(str(edge.stability_score)),
            ),
        )
        return cur.rowcount > 0


def upsert_market_metrics(conn: PgConnection, metrics: list) -> int:
    written = 0
    with conn.cursor() as cur:
        for metric in metrics:
            cur.execute(
                """
                INSERT INTO market_graph_metrics (
                    market_id,
                    domain,
                    out_degree,
                    in_degree,
                    eigenvector_centrality,
                    betweenness_centrality,
                    computed_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (market_id) DO UPDATE SET
                    domain = EXCLUDED.domain,
                    out_degree = EXCLUDED.out_degree,
                    in_degree = EXCLUDED.in_degree,
                    eigenvector_centrality = EXCLUDED.eigenvector_centrality,
                    betweenness_centrality = EXCLUDED.betweenness_centrality,
                    computed_at = NOW()
                """,
                (
                    metric.market_id,
                    metric.domain,
                    metric.out_degree,
                    metric.in_degree,
                    Decimal(str(metric.eigenvector_centrality)),
                    Decimal(str(metric.betweenness_centrality)),
                ),
            )
            written += 1
    return written


def insert_signal_if_changed(conn: PgConnection, signal: MispricingSignal) -> bool:
    reason_json = json.dumps(signal.reason)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO arbitrage_signals (
                parent_market,
                related_market,
                expected_probability,
                observed_probability,
                edge,
                signal,
                confidence,
                reason_json
            )
            SELECT %s, %s, %s, %s, %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1
                FROM arbitrage_signals
                WHERE parent_market = %s
                  AND related_market = %s
                  AND expected_probability = %s
                  AND observed_probability = %s
                  AND edge = %s
                  AND signal = %s
                  AND confidence = %s
                  AND created_at = (
                      SELECT MAX(created_at)
                      FROM arbitrage_signals
                      WHERE parent_market = %s
                        AND related_market = %s
                  )
            )
            """,
            (
                signal.parent_id,
                signal.child_id,
                Decimal(str(signal.expected_probability)),
                Decimal(str(signal.observed_probability)),
                Decimal(str(signal.edge)),
                signal.signal,
                Decimal(str(signal.confidence)),
                reason_json,
                signal.parent_id,
                signal.child_id,
                Decimal(str(signal.expected_probability)),
                Decimal(str(signal.observed_probability)),
                Decimal(str(signal.edge)),
                signal.signal,
                Decimal(str(signal.confidence)),
                signal.parent_id,
                signal.child_id,
            ),
        )
        return cur.rowcount > 0
