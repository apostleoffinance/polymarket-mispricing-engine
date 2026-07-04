"""Backfill probability_history from Polymarket CLOB prices-history API."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import requests
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_batch

from config import (
    BACKFILL_FIDELITY_MINUTES,
    BACKFILL_INCLUDE_CLOSED,
    BACKFILL_MAX_MARKETS,
    BACKFILL_REQUEST_SLEEP_SECONDS,
    BACKFILL_YEARS,
    CLOB_PRICES_HISTORY_URL,
    DOMAINS,
    GAMMA_MARKET_URL,
)


@dataclass(frozen=True)
class MarketForBackfill:
    id: str
    question: str
    yes_clob_token_id: str | None
    volume: float


@dataclass(frozen=True)
class BackfillStats:
    markets_processed: int
    markets_skipped: int
    points_fetched: int
    points_inserted: int
    tokens_synced: int


def parse_clob_token_ids(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    try:
        ids = json.loads(raw)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(ids, list) or not ids:
        return None, None
    if len(ids) >= 2:
        return str(ids[0]), str(ids[1])
    return str(ids[0]), None


def fetch_gamma_market(market_id: str) -> dict[str, Any] | None:
    response = requests.get(f"{GAMMA_MARKET_URL}/{market_id}", timeout=30)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def sync_market_tokens(conn: PgConnection, market_id: str) -> tuple[str | None, str | None]:
    payload = fetch_gamma_market(market_id)
    if payload is None:
        return None, None

    yes_token, no_token = parse_clob_token_ids(payload.get("clobTokenIds"))
    if yes_token is None:
        return None, None

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE markets
            SET yes_clob_token_id = %s,
                no_clob_token_id = %s,
                question = COALESCE(NULLIF(question, ''), %s)
            WHERE id = %s
            """,
            (yes_token, no_token, payload.get("question", ""), market_id),
        )
    return yes_token, no_token


def load_relationship_markets_for_backfill(
    conn: PgConnection,
    *,
    max_markets: int | None,
    include_closed: bool,
) -> list[MarketForBackfill]:
    """Markets appearing in discovered relationships, thinnest history first."""
    closed_filter = "" if include_closed else "AND m.closed IS FALSE"

    query = f"""
        WITH edge_markets AS (
            SELECT DISTINCT parent_market_id AS id
            FROM market_relationships
            WHERE parent_market_id IS NOT NULL
            UNION
            SELECT DISTINCT related_market_id
            FROM market_relationships
            WHERE related_market_id IS NOT NULL
        ),
        history_counts AS (
            SELECT market_id, COUNT(*) AS snapshot_count
            FROM probability_history
            GROUP BY market_id
        )
        SELECT
            m.id,
            m.question,
            m.yes_clob_token_id,
            COALESCE(m.volume, 0),
            COALESCE(h.snapshot_count, 0) AS snapshot_count
        FROM markets m
        JOIN edge_markets em ON em.id = m.id
        LEFT JOIN history_counts h ON h.market_id = m.id
        WHERE 1=1
          {closed_filter}
        ORDER BY snapshot_count ASC, m.volume DESC NULLS LAST
    """
    params: list[Any] = []
    if max_markets is not None:
        query += " LIMIT %s"
        params.append(max_markets)

    with conn.cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

    return [
        MarketForBackfill(
            id=row[0],
            question=row[1] or "",
            yes_clob_token_id=row[2],
            volume=float(row[3] or 0),
        )
        for row in rows
    ]


def load_markets_for_backfill(
    conn: PgConnection,
    *,
    max_markets: int | None,
    include_closed: bool,
) -> list[MarketForBackfill]:
    closed_filter = "" if include_closed else "AND closed IS FALSE"
    domain_filter = "AND domain = ANY(%s)" if DOMAINS else ""

    query = f"""
        SELECT id, question, yes_clob_token_id, COALESCE(volume, 0)
        FROM markets
        WHERE 1=1
          {closed_filter}
          {domain_filter}
        ORDER BY volume DESC NULLS LAST
    """
    params: list[Any] = []
    if DOMAINS:
        params.append(list(DOMAINS))
    if max_markets is not None:
        query += " LIMIT %s"
        params.append(max_markets)

    with conn.cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

    return [
        MarketForBackfill(
            id=row[0],
            question=row[1] or "",
            yes_clob_token_id=row[2],
            volume=float(row[3] or 0),
        )
        for row in rows
    ]


def fetch_clob_price_history(
    yes_token: str,
    *,
    years: int,
    fidelity_minutes: int,
) -> list[tuple[int, float]]:
    points_by_time: dict[int, float] = {}

    def add_points(points: list[tuple[int, float]]) -> None:
        for timestamp, price in points:
            points_by_time[timestamp] = price

    # Best-effort single call for recent max window.
    for params in (
        {"market": yes_token, "interval": "max", "fidelity": fidelity_minutes},
        {"market": yes_token, "interval": "max", "fidelity": 1440},
        {"market": yes_token, "interval": "all", "fidelity": 1440},
    ):
        try:
            response = requests.get(CLOB_PRICES_HISTORY_URL, params=params, timeout=60)
            response.raise_for_status()
            add_points(_parse_history_points(response.json().get("history", [])))
        except requests.RequestException:
            continue

    # Chunked requests — API rejects very long start/end ranges.
    end_dt = datetime.now(UTC)
    start_dt = end_dt - timedelta(days=365 * years)
    chunk_days = 90
    chunk_start = start_dt

    while chunk_start < end_dt:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end_dt)
        try:
            response = requests.get(
                CLOB_PRICES_HISTORY_URL,
                params={
                    "market": yes_token,
                    "startTs": int(chunk_start.timestamp()),
                    "endTs": int(chunk_end.timestamp()),
                    "fidelity": max(fidelity_minutes, 1440),
                },
                timeout=60,
            )
            response.raise_for_status()
            add_points(_parse_history_points(response.json().get("history", [])))
        except requests.RequestException:
            pass

        chunk_start = chunk_end

    return sorted(points_by_time.items())


def _parse_history_points(history: list[dict[str, Any]]) -> list[tuple[int, float]]:
    points: list[tuple[int, float]] = []
    for point in history:
        timestamp = point.get("t")
        price = point.get("p")
        if timestamp is None or price is None:
            continue
        points.append((int(timestamp), float(price)))
    return points


def count_market_history(conn: PgConnection, market_id: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM probability_history WHERE market_id = %s",
            (market_id,),
        )
        return int(cur.fetchone()[0])


def insert_history_points(
    conn: PgConnection,
    market_id: str,
    question: str,
    points: list[tuple[int, float]],
) -> int:
    if not points:
        return 0

    rows = [
        (
            market_id,
            question,
            Decimal(str(price)),
            Decimal(str(max(0.0, min(1.0, 1.0 - price)))),
            datetime.fromtimestamp(timestamp, tz=UTC).replace(
                minute=0, second=0, microsecond=0
            ),
        )
        for timestamp, price in points
    ]

    with conn.cursor() as cur:
        execute_batch(
            cur,
            """
            INSERT INTO probability_history (
                market_id,
                question,
                yes_probability,
                no_probability,
                recorded_at
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (market_id, recorded_at) DO NOTHING
            """,
            rows,
            page_size=500,
        )

    return 0


def backfill_market(
    conn: PgConnection,
    market: MarketForBackfill,
    *,
    years: int,
    fidelity_minutes: int,
) -> tuple[int, int, bool]:
    yes_token = market.yes_clob_token_id
    token_synced = False

    if not yes_token:
        yes_token, _ = sync_market_tokens(conn, market.id)
        token_synced = yes_token is not None

    if not yes_token:
        return 0, 0, token_synced

    before = count_market_history(conn, market.id)
    points = fetch_clob_price_history(
        yes_token,
        years=years,
        fidelity_minutes=fidelity_minutes,
    )
    insert_history_points(conn, market.id, market.question, points)
    after = count_market_history(conn, market.id)

    return len(points), after - before, token_synced


def run_backfill(
    conn: PgConnection,
    *,
    years: int = BACKFILL_YEARS,
    fidelity_minutes: int = BACKFILL_FIDELITY_MINUTES,
    max_markets: int | None = BACKFILL_MAX_MARKETS,
    include_closed: bool = BACKFILL_INCLUDE_CLOSED,
    sleep_seconds: float = BACKFILL_REQUEST_SLEEP_SECONDS,
    relationship_markets: bool = False,
) -> BackfillStats:
    loader = (
        load_relationship_markets_for_backfill
        if relationship_markets
        else load_markets_for_backfill
    )
    markets = loader(
        conn,
        max_markets=max_markets,
        include_closed=include_closed,
    )

    processed = 0
    skipped = 0
    fetched = 0
    inserted = 0
    tokens_synced = 0

    for index, market in enumerate(markets, start=1):
        try:
            point_count, inserted_count, synced = backfill_market(
                conn,
                market,
                years=years,
                fidelity_minutes=fidelity_minutes,
            )
            conn.commit()

            if point_count == 0 and inserted_count == 0:
                skipped += 1
            else:
                processed += 1

            fetched += point_count
            inserted += inserted_count
            if synced:
                tokens_synced += 1

            print(
                f"[{index}/{len(markets)}] {market.id} | "
                f"fetched={point_count} inserted={inserted_count}"
            )
        except requests.RequestException as error:
            conn.rollback()
            skipped += 1
            print(f"[{index}/{len(markets)}] {market.id} | error: {error}")
        except Exception as error:
            conn.rollback()
            skipped += 1
            print(f"[{index}/{len(markets)}] {market.id} | error: {error}")

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return BackfillStats(
        markets_processed=processed,
        markets_skipped=skipped,
        points_fetched=fetched,
        points_inserted=inserted,
        tokens_synced=tokens_synced,
    )
