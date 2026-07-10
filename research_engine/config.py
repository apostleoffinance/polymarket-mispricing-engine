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
# Use measured lead/lag to set evaluation horizon (max with BACKTEST_HORIZON_MINUTES).
BACKTEST_USE_LAG_HORIZON: bool = True
# Skip edges with known stability below this (0 = disabled; unknown/0.0 kept).
BACKTEST_MIN_STABILITY: float = 0.35

# Grid search defaults (run_optimize_backtest.py).
OPTIMIZE_MIN_SIGNALS: int = 50
OPTIMIZE_TARGET_WIN_RATE: float = 0.50

# Edge dynamics: lead/lag and rolling stability.
LEAD_LAG_MAX_HOURS: int = 12
STABILITY_ROLLING_WINDOW: int = 24
STABILITY_MIN_WINDOWS: int = 5
MIN_STABILITY_SCORE: float = 0.35

# Candidate relationship pipeline (propose → validate → promote).
CANDIDATE_TOKEN_MIN_OVERLAP: int = 2
CANDIDATE_MAX_PER_MARKET: int = 8
CANDIDATE_MAX_PROPOSALS: int = 200
VALIDATE_CROSS_DOMAIN: bool = True

# Optional LLM hypothesis agent (writes candidates only; never promotes).
HYPOTHESIS_LLM_ENABLED: bool = True
# Try providers in order; skip any whose API key is missing.
HYPOTHESIS_LLM_PROVIDERS: tuple[str, ...] = ("openai", "gemini")
HYPOTHESIS_OPENAI_MODEL: str = "gpt-4o-mini"
HYPOTHESIS_GEMINI_MODEL: str = "gemini-2.0-flash"
HYPOTHESIS_LLM_MAX_MARKETS: int = 25
HYPOTHESIS_LLM_MAX_SUGGESTIONS: int = 40
