"""PostgreSQL loaders for the graph engine."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as PgConnection

from models import MarketNode

load_dotenv(Path(__file__).resolve().parents[1] / "rust_engine" / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgres://localhost:5433/polymarket")


def connect() -> PgConnection:
    return psycopg2.connect(DATABASE_URL)


def load_markets(
    conn: PgConnection,
    domains: tuple[str, ...],
    *,
    max_per_domain: int,
    min_volume: float = 0.0,
) -> list[MarketNode]:
    """Load top markets by volume within each domain."""
    query = """
        SELECT id, question, domain, volume, liquidity
        FROM (
            SELECT
                id,
                question,
                domain,
                volume,
                liquidity,
                ROW_NUMBER() OVER (
                    PARTITION BY domain
                    ORDER BY volume DESC NULLS LAST
                ) AS rn
            FROM markets
            WHERE domain = ANY(%s)
              AND active IS TRUE
              AND closed IS FALSE
              AND COALESCE(volume, 0) >= %s
        ) ranked
        WHERE rn <= %s
        ORDER BY domain, volume DESC NULLS LAST
    """
    with conn.cursor() as cur:
        cur.execute(query, (list(domains), min_volume, max_per_domain))
        rows = cur.fetchall()

    return [
        MarketNode(
            id=row[0],
            question=row[1],
            domain=row[2],
            volume=Decimal(str(row[3] or 0)),
            liquidity=Decimal(str(row[4] or 0)),
        )
        for row in rows
    ]


def load_latest_prices(conn: PgConnection, market_ids: list[str]) -> pd.Series:
    """Latest yes probability per market id."""
    if not market_ids:
        return pd.Series(dtype=float)

    query = """
        SELECT DISTINCT ON (market_id)
            market_id,
            yes_probability
        FROM probability_history
        WHERE market_id = ANY(%s)
        ORDER BY market_id, recorded_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(query, (market_ids,))
        rows = cur.fetchall()

    return pd.Series(
        {market_id: float(yes) for market_id, yes in rows},
        dtype=float,
    )


def load_price_history(conn: PgConnection, market_ids: list[str]) -> pd.DataFrame:
    """
    Long-format history: recorded_at, market_id, yes_probability.
  """
    if not market_ids:
        return pd.DataFrame(columns=["recorded_at", "market_id", "yes_probability"])

    query = """
        SELECT recorded_at, market_id, yes_probability
        FROM probability_history
        WHERE market_id = ANY(%s)
        ORDER BY recorded_at
    """
    with conn.cursor() as cur:
        cur.execute(query, (market_ids,))
        rows = cur.fetchall()

    return pd.DataFrame(
        rows, columns=["recorded_at", "market_id", "yes_probability"]
    )


def bucket_history_to_hourly(history: pd.DataFrame) -> pd.DataFrame:
    """Collapse snapshots to hourly buckets (last observation per hour)."""
    if history.empty:
        return history

    bucketed = history.copy()
    bucketed["recorded_at"] = pd.to_datetime(bucketed["recorded_at"], utc=True).dt.floor("h")
    grouped = (
        bucketed.sort_values("recorded_at")
        .groupby(["recorded_at", "market_id"], as_index=False)
    )
    if "question" in bucketed.columns:
        return grouped.agg({"yes_probability": "last", "question": "last"})
    return grouped.agg({"yes_probability": "last"})


def load_price_matrix(history: pd.DataFrame, *, hourly: bool = True) -> pd.DataFrame:
    """
    Wide matrix of yes probabilities aligned on time, forward-filled.
    """
    if history.empty:
        return pd.DataFrame()

    aligned = bucket_history_to_hourly(history) if hourly else history.copy()

    wide = (
        aligned.pivot(index="recorded_at", columns="market_id", values="yes_probability")
        .sort_index()
        .astype(float)
        .ffill()
    )
    return wide
