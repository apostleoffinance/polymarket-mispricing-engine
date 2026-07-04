#!/usr/bin/env python3
"""Read-only API for the research dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import DOMAINS
from db import connect

app = FastAPI(title="Polymarket Research API", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

LIVE_SIGNAL_FILTER = """
    parent_market ~ '^[0-9]+$'
    AND related_market ~ '^[0-9]+$'
"""


def _normalize_domain(domain: str | None) -> str | None:
    if not domain or domain.lower() == "all":
        return None
    return domain


def _domain_filter_sql(domain: str | None, column: str) -> tuple[str, list[str]]:
    if domain is None:
        return "", []
    return f" AND {column} = %s", [domain]


def _fetch_live_by_domain(cur) -> dict[str, dict]:
    cur.execute(
        f"""
        SELECT
            COALESCE(parent_m.domain, 'unknown') AS domain,
            COUNT(*) AS signal_count,
            COUNT(*) FILTER (WHERE s.signal = 'BUY') AS buy_count,
            COUNT(*) FILTER (WHERE s.signal = 'SELL') AS sell_count,
            COUNT(*) FILTER (WHERE s.signal = 'HOLD') AS hold_count
        FROM arbitrage_signals s
        LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
        WHERE {LIVE_SIGNAL_FILTER}
        GROUP BY COALESCE(parent_m.domain, 'unknown')
        ORDER BY domain
        """
    )
    return {
        row[0]: {
            "signals": row[1],
            "buy": row[2],
            "sell": row[3],
            "hold": row[4],
        }
        for row in cur.fetchall()
    }


def _fetch_backtest_by_domain(cur) -> tuple[int | None, dict[str, dict]]:
    cur.execute("SELECT MAX(id) FROM backtest_runs")
    latest_run = cur.fetchone()[0]
    if latest_run is None:
        return None, {}

    cur.execute(
        """
        SELECT
            COALESCE(domain, 'unknown') AS domain,
            COUNT(*) AS actionable,
            COUNT(*) FILTER (WHERE directional_win) AS wins,
            COUNT(*) FILTER (WHERE edge_closed) AS edge_closed,
            AVG(ABS(edge_at_t)) AS mean_edge_at,
            AVG(ABS(edge_at_t_plus)) AS mean_edge_after,
            AVG(minutes_to_reprice) AS mean_reprice
        FROM backtest_results
        WHERE run_id = %s
        GROUP BY COALESCE(domain, 'unknown')
        ORDER BY domain
        """,
        (latest_run,),
    )
    rows = {
        row[0]: {
            "actionable_signals": row[1],
            "directional_wins": row[2],
            "directional_win_rate": row[2] / row[1] if row[1] else 0.0,
            "edge_closed_count": row[3],
            "edge_closed_rate": row[3] / row[1] if row[1] else 0.0,
            "mean_edge_at_signal": float(row[4] or 0),
            "mean_edge_after": float(row[5] or 0),
            "mean_minutes_to_reprice": float(row[6]) if row[6] is not None else None,
        }
        for row in cur.fetchall()
    }
    return latest_run, rows


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": 2, "features": ["domains", "domain_filter"]}


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/api/domains")
def domain_stats() -> dict:
    """Per-domain live signal counts and latest-backtest win rates."""
    with connect() as conn:
        with conn.cursor() as cur:
            live_rows = _fetch_live_by_domain(cur)
            latest_run, backtest_rows = _fetch_backtest_by_domain(cur)

    categories = sorted(set(live_rows) | set(backtest_rows) | set(DOMAINS))
    categories = [d for d in categories if d != "unknown"] + (
        ["unknown"] if "unknown" in categories else []
    )

    return {
        "categories": categories,
        "live": live_rows,
        "backtest": backtest_rows,
        "latest_run_id": latest_run,
    }


@app.get("/api/overview")
def overview(domain: str | None = Query(default=None)) -> dict:
    domain = _normalize_domain(domain)
    domain_sql, domain_params = _domain_filter_sql(domain, "m.domain")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM markets m
                WHERE domain IS NOT NULL
                  {domain_sql}
                """,
                tuple(domain_params),
            )
            markets = cur.fetchone()[0]

            if domain:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM probability_history ph
                    JOIN markets m ON m.id = ph.market_id
                    WHERE m.domain = %s
                    """,
                    (domain,),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM probability_history")
            snapshots = cur.fetchone()[0]

            if domain:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM market_relationships r
                    JOIN markets m ON m.id = r.parent_market_id
                    WHERE r.parent_market_id IS NOT NULL
                      AND m.domain = %s
                    """,
                    (domain,),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM market_relationships
                    WHERE parent_market_id IS NOT NULL
                    """
                )
            relationships = cur.fetchone()[0]

            signal_domain_sql, signal_domain_params = _domain_filter_sql(
                domain, "parent_m.domain"
            )
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM arbitrage_signals s
                LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
                WHERE {LIVE_SIGNAL_FILTER}
                  {signal_domain_sql}
                """,
                tuple(signal_domain_params),
            )
            signals = cur.fetchone()[0]

            if domain:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE n >= 100),
                        ROUND(AVG(n), 1),
                        MAX(n)
                    FROM (
                        SELECT ph.market_id, COUNT(*) AS n
                        FROM probability_history ph
                        JOIN markets m ON m.id = ph.market_id
                        WHERE m.domain = %s
                        GROUP BY ph.market_id
                    ) t
                    """,
                    (domain,),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE n >= 100),
                        ROUND(AVG(n), 1),
                        MAX(n)
                    FROM (
                        SELECT market_id, COUNT(*) AS n
                        FROM probability_history
                        GROUP BY market_id
                    ) t
                    """
                )
            depth = cur.fetchone()

            cur.execute(
                """
                SELECT domain, COUNT(*)
                FROM markets
                WHERE domain IS NOT NULL
                GROUP BY domain
                ORDER BY domain
                """
            )
            domains = {row[0]: row[1] for row in cur.fetchall()}

            live_by_domain = _fetch_live_by_domain(cur)
            latest_run_id, backtest_by_domain = _fetch_backtest_by_domain(cur)

    return {
        "domain": domain,
        "markets": markets,
        "snapshots": snapshots,
        "relationships": relationships,
        "signals": signals,
        "markets_with_100_plus_snapshots": depth[0] if depth else 0,
        "avg_snapshots_per_market": float(depth[1] or 0) if depth else 0,
        "max_snapshots_per_market": depth[2] if depth else 0,
        "domains": domains,
        "live_by_domain": live_by_domain,
        "backtest_by_domain": backtest_by_domain,
        "latest_backtest_run_id": latest_run_id,
    }


@app.get("/api/signals")
def signals(
    limit: int = 20,
    domain: str | None = Query(default=None),
) -> list[dict]:
    domain = _normalize_domain(domain)
    domain_sql, domain_params = _domain_filter_sql(domain, "parent_m.domain")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    s.parent_market,
                    parent_m.question,
                    parent_m.domain,
                    s.related_market,
                    child_m.question,
                    s.expected_probability,
                    s.observed_probability,
                    s.edge,
                    s.confidence,
                    s.signal,
                    s.created_at
                FROM arbitrage_signals s
                LEFT JOIN markets parent_m ON parent_m.id = s.parent_market
                LEFT JOIN markets child_m ON child_m.id = s.related_market
                WHERE {LIVE_SIGNAL_FILTER}
                  {domain_sql}
                ORDER BY s.created_at DESC
                LIMIT %s
                """,
                (*domain_params, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "parent_id": row[0],
            "parent_question": row[1],
            "domain": row[2],
            "child_id": row[3],
            "child_question": row[4],
            "expected": float(row[5]) if row[5] is not None else None,
            "observed": float(row[6]) if row[6] is not None else None,
            "edge": float(row[7]) if row[7] is not None else None,
            "confidence": float(row[8]) if row[8] is not None else None,
            "signal": row[9],
            "created_at": row[10].isoformat() if row[10] else None,
        }
        for row in rows
    ]


@app.get("/api/backtest/latest")
def backtest_latest(domain: str | None = Query(default=None)) -> dict | None:
    domain = _normalize_domain(domain)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    started_at,
                    total_evaluations,
                    actionable_signals,
                    directional_wins,
                    edge_closed_count,
                    directional_win_rate,
                    edge_closed_rate,
                    mean_edge_at_signal,
                    mean_edge_after,
                    mean_minutes_to_reprice
                FROM backtest_runs
                ORDER BY id DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()

            if row is None:
                return None

            run_id = row[0]
            result: dict = {
                "id": run_id,
                "started_at": row[1].isoformat() if row[1] else None,
                "total_evaluations": row[2],
                "actionable_signals": row[3],
                "directional_wins": row[4],
                "edge_closed_count": row[5],
                "directional_win_rate": float(row[6] or 0),
                "edge_closed_rate": float(row[7] or 0),
                "mean_edge_at_signal": float(row[8] or 0),
                "mean_edge_after": float(row[9] or 0),
                "mean_minutes_to_reprice": float(row[10]) if row[10] is not None else None,
                "domain": domain,
            }

            if domain is not None:
                cur.execute(
                    """
                    SELECT
                        COUNT(*),
                        COUNT(*) FILTER (WHERE directional_win),
                        COUNT(*) FILTER (WHERE edge_closed),
                        AVG(ABS(edge_at_t)),
                        AVG(ABS(edge_at_t_plus)),
                        AVG(minutes_to_reprice)
                    FROM backtest_results
                    WHERE run_id = %s AND domain = %s
                    """,
                    (run_id, domain),
                )
                stats = cur.fetchone()
                actionable = stats[0] or 0
                wins = stats[1] or 0
                closed = stats[2] or 0
                result.update(
                    {
                        "actionable_signals": actionable,
                        "directional_wins": wins,
                        "edge_closed_count": closed,
                        "directional_win_rate": wins / actionable if actionable else 0.0,
                        "edge_closed_rate": closed / actionable if actionable else 0.0,
                        "mean_edge_at_signal": float(stats[3] or 0),
                        "mean_edge_after": float(stats[4] or 0),
                        "mean_minutes_to_reprice": float(stats[5])
                        if stats[5] is not None
                        else None,
                    }
                )

    return result


@app.get("/api/backtest/results")
def backtest_results(
    limit: int = 50,
    domain: str | None = Query(default=None),
) -> list[dict]:
    domain = _normalize_domain(domain)
    domain_sql, domain_params = _domain_filter_sql(domain, "r.domain")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    r.parent_market_id,
                    parent_m.question,
                    r.child_market_id,
                    child_m.question,
                    r.domain,
                    r.signal,
                    r.edge_at_t,
                    r.edge_at_t_plus,
                    r.directional_win,
                    r.edge_closed,
                    r.simple_pnl,
                    r.signal_time
                FROM backtest_results r
                LEFT JOIN markets parent_m ON parent_m.id = r.parent_market_id
                LEFT JOIN markets child_m ON child_m.id = r.child_market_id
                WHERE r.run_id = (SELECT MAX(id) FROM backtest_runs)
                  {domain_sql}
                ORDER BY ABS(r.edge_at_t) DESC
                LIMIT %s
                """,
                (*domain_params, limit),
            )
            rows = cur.fetchall()

    return [
        {
            "parent_id": row[0],
            "parent_question": row[1],
            "child_id": row[2],
            "child_question": row[3],
            "domain": row[4],
            "signal": row[5],
            "edge_at_t": float(row[6]) if row[6] is not None else None,
            "edge_at_t_plus": float(row[7]) if row[7] is not None else None,
            "directional_win": row[8],
            "edge_closed": row[9],
            "simple_pnl": float(row[10]) if row[10] is not None else None,
            "signal_time": row[11].isoformat() if row[11] else None,
        }
        for row in rows
    ]


def main() -> None:
    import uvicorn

    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
