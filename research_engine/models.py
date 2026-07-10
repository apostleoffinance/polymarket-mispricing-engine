"""Market entities used by the graph engine."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MarketNode:
    id: str
    question: str
    domain: str
    volume: Decimal
    liquidity: Decimal
    yes_probability: Decimal | None = None


@dataclass(frozen=True)
class DiscoveredEdge:
    parent_id: str
    parent_label: str
    child_id: str
    child_label: str
    relationship_type: str
    strength: float
    correlation: float
    correlation_shrunk: float
    beta: float
    intercept: float
    conditional_slope: float
    n_observations: int
    lag_minutes: int = 0
    lead_correlation: float = 0.0
    stability_score: float = 0.0


@dataclass(frozen=True)
class RelationshipCandidate:
    parent_id: str
    child_id: str
    parent_question: str
    child_question: str
    parent_domain: str
    child_domain: str
    source: str
    rationale: str
    confidence: float = 0.0


@dataclass(frozen=True)
class NodeMetrics:
    market_id: str
    domain: str
    out_degree: int
    in_degree: int
    eigenvector_centrality: float
    betweenness_centrality: float
