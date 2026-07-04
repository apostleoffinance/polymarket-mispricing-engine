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
CORRELATION_THRESHOLD: float = 0.55

# Composite strength floor for edge retention.
MIN_STRENGTH: float = 0.20

MIN_VOLUME: float = 0.0

EDGE_BUY_THRESHOLD: float = 0.10
EDGE_SELL_THRESHOLD: float = -0.10

# Minimum confidence to emit BUY/SELL (else HOLD).
MIN_SIGNAL_CONFIDENCE: float = 0.35

MAX_EDGES_PER_DOMAIN: int = 50

# Historical backfill via CLOB prices-history API.
BACKFILL_YEARS: int = 3
BACKFILL_FIDELITY_MINUTES: int = 60
BACKFILL_MAX_MARKETS: int | None = None
BACKFILL_REQUEST_SLEEP_SECONDS: float = 0.05
BACKFILL_INCLUDE_CLOSED: bool = True

GAMMA_MARKET_URL: str = "https://gamma-api.polymarket.com/markets"
CLOB_PRICES_HISTORY_URL: str = "https://clob.polymarket.com/prices-history"

# Backtest: walk-forward training window and outcome horizon.
BACKTEST_MIN_TRAIN_SNAPSHOTS: int = 5
BACKTEST_HORIZON_MINUTES: int = 60
BACKTEST_EDGE_CLOSE_FRACTION: float = 0.5

# Optimized backtest gates (live signals keep stricter EDGE_* / MIN_SIGNAL_CONFIDENCE).
BACKTEST_CORRELATION_THRESHOLD: float = 0.55
BACKTEST_EDGE_BUY_THRESHOLD: float = 0.15
BACKTEST_EDGE_SELL_THRESHOLD: float = -0.15
BACKTEST_MIN_SIGNAL_CONFIDENCE: float = 0.45
BACKTEST_MIN_OBSERVATIONS: int = 10

# Structural backtest options.
BACKTEST_WALK_FORWARD_ONLY: bool = True
BACKTEST_WIN_REQUIRES_PNL: bool = True
# None = all domains; set e.g. ("politics", "geopolitics") to exclude noisy domains.
BACKTEST_DOMAINS: tuple[str, ...] | None = None

# Grid search defaults (run_optimize_backtest.py).
OPTIMIZE_MIN_SIGNALS: int = 50
OPTIMIZE_TARGET_WIN_RATE: float = 0.50
