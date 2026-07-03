"""Graph engine configuration."""

DOMAINS: tuple[str, ...] = (
    "politics",
    "football",
    "crypto",
    "macro",
    "geopolitics",
)

MAX_MARKETS_PER_DOMAIN: int = 200

# Minimum aligned time buckets with data for a pair.
MIN_OVERLAPPING_SNAPSHOTS: int = 10

# Shrinkage: r_adj = r * sqrt(n / (n + CORRELATION_SHRINKAGE_K))
CORRELATION_SHRINKAGE_K: int = 10

# |shrunk correlation| must meet this to create an edge.
CORRELATION_THRESHOLD: float = 0.5

# Composite strength floor for edge retention.
MIN_STRENGTH: float = 0.15

MIN_VOLUME: float = 0.0

EDGE_BUY_THRESHOLD: float = 0.10
EDGE_SELL_THRESHOLD: float = -0.10

# Minimum confidence to emit BUY/SELL (else HOLD).
MIN_SIGNAL_CONFIDENCE: float = 0.35

MAX_EDGES_PER_DOMAIN: int = 50
