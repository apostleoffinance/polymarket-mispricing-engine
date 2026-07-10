"""Evidence-backed signal explanations for the dashboard / research UI."""

from __future__ import annotations

from models import DiscoveredEdge
from signals import MispricingSignal


def explain_signal(
    signal: MispricingSignal,
    edge: DiscoveredEdge | None = None,
    *,
    parent_move_6h: float | None = None,
) -> str:
    """
    Build a grounded explanation from stored edge statistics.

    No LLM required — every claim maps to a numeric field.
    """
    direction = "above" if signal.edge > 0 else "below"
    parts = [
        (
            f"{signal.signal}: child trades {direction} model fair value "
            f"(expected {signal.expected_probability:.2f}, "
            f"observed {signal.observed_probability:.2f}, "
            f"edge {signal.edge:+.3f}, confidence {signal.confidence:.2f})."
        )
    ]

    if edge is not None:
        lag_hours = edge.lag_minutes / 60.0
        if abs(edge.lag_minutes) >= 60:
            if edge.lag_minutes > 0:
                parts.append(
                    f"Parent historically leads child by ~{lag_hours:.0f}h "
                    f"(lead corr {edge.lead_correlation:+.2f})."
                )
            else:
                parts.append(
                    f"Child historically leads parent by ~{abs(lag_hours):.0f}h "
                    f"(lead corr {edge.lead_correlation:+.2f})."
                )
        else:
            parts.append(
                f"Relationship is roughly contemporaneous "
                f"(corr {edge.correlation_shrunk:+.2f}, β={edge.beta:+.2f})."
            )

        parts.append(
            f"Edge stability score {edge.stability_score:.2f} over "
            f"{edge.n_observations} aligned snapshots."
        )

    if parent_move_6h is not None:
        parts.append(
            f"Parent yes-probability moved {parent_move_6h:+.1%} over the last ~6h."
        )

    return " ".join(parts)


def attach_explanations(
    signals: list[MispricingSignal],
    edges: list[DiscoveredEdge],
) -> list[MispricingSignal]:
    """Return new signals with explanation text merged into reason_json."""
    edge_by_pair = {(edge.parent_id, edge.child_id): edge for edge in edges}
    enriched: list[MispricingSignal] = []
    for signal in signals:
        edge = edge_by_pair.get((signal.parent_id, signal.child_id))
        explanation = explain_signal(signal, edge)
        reason = dict(signal.reason)
        reason["explanation"] = explanation
        if edge is not None:
            reason["lag_minutes"] = edge.lag_minutes
            reason["lead_correlation"] = round(edge.lead_correlation, 4)
            reason["stability_score"] = round(edge.stability_score, 4)
        enriched.append(
            MispricingSignal(
                parent_id=signal.parent_id,
                child_id=signal.child_id,
                expected_probability=signal.expected_probability,
                observed_probability=signal.observed_probability,
                edge=signal.edge,
                signal=signal.signal,
                confidence=signal.confidence,
                reason=reason,
            )
        )
    return enriched
