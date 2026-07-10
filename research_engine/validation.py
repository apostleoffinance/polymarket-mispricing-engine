"""Validate candidate relationships and promote evidence-backed edges."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from psycopg2.extensions import connection as PgConnection

from config import (
    CORRELATION_THRESHOLD,
    MIN_STABILITY_SCORE,
    MIN_STRENGTH,
    VALIDATE_CROSS_DOMAIN,
)
from discovery import _orient_parent_child, _short_label
from models import DiscoveredEdge, MarketNode, RelationshipCandidate
from statistics import compute_pair_statistics


def upsert_candidate(conn: PgConnection, candidate: RelationshipCandidate) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO candidate_relationships (
                parent_market_id,
                child_market_id,
                parent_question,
                child_question,
                parent_domain,
                child_domain,
                source,
                rationale,
                status,
                confidence
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'proposed', %s)
            ON CONFLICT (parent_market_id, child_market_id, source)
            DO UPDATE SET
                parent_question = EXCLUDED.parent_question,
                child_question = EXCLUDED.child_question,
                parent_domain = EXCLUDED.parent_domain,
                child_domain = EXCLUDED.child_domain,
                rationale = EXCLUDED.rationale,
                confidence = EXCLUDED.confidence,
                updated_at = NOW()
            WHERE candidate_relationships.status IN ('proposed', 'rejected')
            """,
            (
                candidate.parent_id,
                candidate.child_id,
                candidate.parent_question,
                candidate.child_question,
                candidate.parent_domain,
                candidate.child_domain,
                candidate.source,
                candidate.rationale,
                Decimal(str(candidate.confidence)),
            ),
        )
        return cur.rowcount > 0


def load_pending_candidates(
    conn: PgConnection,
    *,
    limit: int = 500,
) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                parent_market_id,
                child_market_id,
                parent_question,
                child_question,
                parent_domain,
                child_domain,
                source,
                rationale,
                confidence
            FROM candidate_relationships
            WHERE status = 'proposed'
            ORDER BY confidence DESC NULLS LAST, id ASC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "parent_market_id": row[1],
            "child_market_id": row[2],
            "parent_question": row[3],
            "child_question": row[4],
            "parent_domain": row[5],
            "child_domain": row[6],
            "source": row[7],
            "rationale": row[8],
            "confidence": float(row[9] or 0.0),
        }
        for row in rows
    ]


def _mark_candidate(
    conn: PgConnection,
    candidate_id: int,
    *,
    status: str,
    edge: DiscoveredEdge | None = None,
    rejection_reason: str | None = None,
) -> None:
    with conn.cursor() as cur:
        if edge is None:
            cur.execute(
                """
                UPDATE candidate_relationships
                SET status = %s,
                    rejection_reason = %s,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, rejection_reason, candidate_id),
            )
            return

        cur.execute(
            """
            UPDATE candidate_relationships
            SET status = %s,
                rejection_reason = NULL,
                correlation = %s,
                correlation_shrunk = %s,
                beta = %s,
                intercept = %s,
                lag_minutes = %s,
                lead_correlation = %s,
                stability_score = %s,
                n_observations = %s,
                strength = %s,
                parent_market_id = %s,
                child_market_id = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (
                status,
                Decimal(str(edge.correlation)),
                Decimal(str(edge.correlation_shrunk)),
                Decimal(str(edge.beta)),
                Decimal(str(edge.intercept)),
                edge.lag_minutes,
                Decimal(str(edge.lead_correlation)),
                Decimal(str(edge.stability_score)),
                edge.n_observations,
                Decimal(str(edge.strength)),
                edge.parent_id,
                edge.child_id,
                candidate_id,
            ),
        )


def build_edge_from_pair(
    parent: MarketNode,
    child: MarketNode,
    price_matrix: pd.DataFrame,
    *,
    discovery_source: str = "token_overlap",
) -> DiscoveredEdge | None:
    if parent.id not in price_matrix.columns or child.id not in price_matrix.columns:
        return None

    # Prefer orientation where the parent leads the child when lag is informative.
    stats_ab = compute_pair_statistics(price_matrix[parent.id], price_matrix[child.id])
    stats_ba = compute_pair_statistics(price_matrix[child.id], price_matrix[parent.id])
    if stats_ab is None and stats_ba is None:
        return None

    use_ab = True
    if stats_ab is None:
        use_ab = False
    elif stats_ba is not None:
        # Positive lag_minutes means first series leads second.
        if stats_ba.lag_minutes > 0 and stats_ab.lag_minutes <= 0:
            use_ab = False
        elif abs(stats_ba.lead_correlation) > abs(stats_ab.lead_correlation) + 0.05:
            if stats_ba.lag_minutes >= stats_ab.lag_minutes:
                use_ab = False

    if use_ab:
        oriented_parent, oriented_child, stats = parent, child, stats_ab
    else:
        oriented_parent, oriented_child, stats = child, parent, stats_ba

    assert stats is not None
    rel_type = (
        "discovered_positive" if stats.beta >= 0 else "discovered_negative"
    )
    return DiscoveredEdge(
        parent_id=oriented_parent.id,
        parent_label=_short_label(oriented_parent.question),
        child_id=oriented_child.id,
        child_label=_short_label(oriented_child.question),
        relationship_type=rel_type,
        strength=stats.strength,
        correlation=stats.correlation,
        correlation_shrunk=stats.correlation_shrunk,
        beta=stats.beta,
        intercept=stats.intercept,
        conditional_slope=stats.conditional_slope,
        n_observations=stats.n_observations,
        lag_minutes=stats.lag_minutes,
        lead_correlation=stats.lead_correlation,
        stability_score=stats.stability_score,
        discovery_source=discovery_source,
    )


def edge_passes_gates(edge: DiscoveredEdge) -> tuple[bool, str | None]:
    if abs(edge.correlation_shrunk) < CORRELATION_THRESHOLD:
        return False, (
            f"correlation_shrunk {edge.correlation_shrunk:.3f} "
            f"< {CORRELATION_THRESHOLD}"
        )
    if edge.strength < MIN_STRENGTH:
        return False, f"strength {edge.strength:.3f} < {MIN_STRENGTH}"
    if edge.stability_score < MIN_STABILITY_SCORE:
        return False, (
            f"stability {edge.stability_score:.3f} < {MIN_STABILITY_SCORE}"
        )
    return True, None


def validate_pending_candidates(
    conn: PgConnection,
    markets: list[MarketNode],
    price_matrix: pd.DataFrame,
    *,
    allow_cross_domain: bool = VALIDATE_CROSS_DOMAIN,
) -> tuple[list[DiscoveredEdge], dict[str, int]]:
    """
    Statistically validate proposed candidates.

    Returns promoted edges and counts by outcome.
    """
    market_by_id = {market.id: market for market in markets}
    pending = load_pending_candidates(conn)
    promoted: list[DiscoveredEdge] = []
    counts = {"validated": 0, "rejected": 0, "promoted": 0, "skipped": 0}

    for row in pending:
        parent = market_by_id.get(row["parent_market_id"])
        child = market_by_id.get(row["child_market_id"])
        if parent is None or child is None:
            _mark_candidate(
                conn,
                row["id"],
                status="rejected",
                rejection_reason="market_not_in_scope",
            )
            counts["rejected"] += 1
            continue

        if not allow_cross_domain and parent.domain != child.domain:
            _mark_candidate(
                conn,
                row["id"],
                status="rejected",
                rejection_reason="cross_domain_disabled",
            )
            counts["rejected"] += 1
            continue

        # Re-orient by volume first, then lead/lag inside build_edge_from_pair.
        oriented_parent, oriented_child = _orient_parent_child(parent, child)
        edge = build_edge_from_pair(
            oriented_parent,
            oriented_child,
            price_matrix,
            discovery_source=str(row.get("source") or "token_overlap"),
        )
        if edge is None:
            _mark_candidate(
                conn,
                row["id"],
                status="rejected",
                rejection_reason="insufficient_history",
            )
            counts["rejected"] += 1
            continue

        ok, reason = edge_passes_gates(edge)
        if not ok:
            _mark_candidate(
                conn,
                row["id"],
                status="rejected",
                rejection_reason=reason,
            )
            counts["rejected"] += 1
            continue

        _mark_candidate(conn, row["id"], status="promoted", edge=edge)
        counts["validated"] += 1
        counts["promoted"] += 1
        promoted.append(edge)

    return promoted, counts
