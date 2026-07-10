"""Walk-forward backtesting for mispricing signals."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal

import pandas as pd
from psycopg2.extensions import connection as PgConnection

from config import (
    BACKTEST_CORRELATION_THRESHOLD,
    BACKTEST_DOMAINS,
    BACKTEST_EDGE_BUY_THRESHOLD,
    BACKTEST_EDGE_CLOSE_FRACTION,
    BACKTEST_EDGE_SELL_THRESHOLD,
    BACKTEST_HORIZON_MINUTES,
    BACKTEST_MIN_OBSERVATIONS,
    BACKTEST_MIN_SIGNAL_CONFIDENCE,
    BACKTEST_MIN_TRAIN_SNAPSHOTS,
    BACKTEST_WALK_FORWARD_ONLY,
    BACKTEST_WIN_REQUIRES_PNL,
    MIN_STRENGTH,
)
from db import load_price_matrix
from models import DiscoveredEdge
from statistics import compute_pair_statistics, expected_from_regression

EvaluationMode = Literal["walk_forward", "replay"]


@dataclass(frozen=True)
class BacktestSettings:
    correlation_threshold: float = BACKTEST_CORRELATION_THRESHOLD
    edge_buy_threshold: float = BACKTEST_EDGE_BUY_THRESHOLD
    edge_sell_threshold: float = BACKTEST_EDGE_SELL_THRESHOLD
    min_signal_confidence: float = BACKTEST_MIN_SIGNAL_CONFIDENCE
    min_strength: float = MIN_STRENGTH
    min_train_snapshots: int = BACKTEST_MIN_TRAIN_SNAPSHOTS
    min_observations: int = BACKTEST_MIN_OBSERVATIONS
    horizon_minutes: int = BACKTEST_HORIZON_MINUTES
    walk_forward_only: bool = BACKTEST_WALK_FORWARD_ONLY
    win_requires_pnl: bool = BACKTEST_WIN_REQUIRES_PNL
    domains: tuple[str, ...] | None = BACKTEST_DOMAINS

    @classmethod
    def from_config(cls) -> BacktestSettings:
        return cls()

    def with_overrides(self, **kwargs: object) -> BacktestSettings:
        return replace(self, **kwargs)


@dataclass(frozen=True)
class BacktestOutcome:
    parent_market_id: str
    child_market_id: str
    domain: str | None
    signal_time: pd.Timestamp
    horizon_minutes: int
    signal: str
    expected_probability: float
    observed_at_t: float
    observed_at_t_plus: float
    edge_at_t: float
    edge_at_t_plus: float
    confidence: float
    directional_win: bool
    edge_closed: bool
    minutes_to_reprice: float | None
    simple_pnl: float
    evaluation_mode: EvaluationMode


@dataclass(frozen=True)
class BacktestSummary:
    total_evaluations: int
    actionable_signals: int
    directional_wins: int
    edge_closed_count: int
    directional_win_rate: float
    edge_closed_rate: float
    mean_edge_at_signal: float
    mean_edge_after: float
    mean_minutes_to_reprice: float | None


@dataclass(frozen=True)
class BacktestDiagnostics:
    pairs_evaluated: int
    pairs_with_history: int
    pairs_walk_forward: int
    pairs_replay: int
    walk_forward_signals: int
    replay_signals: int
    walk_forward_summary: BacktestSummary
    replay_summary: BacktestSummary
    domain_summaries: dict[str, BacktestSummary]


def compute_confidence(
    edge: DiscoveredEdge,
    parent_centrality: float,
) -> float:
    sample_factor = min(1.0, edge.n_observations / 50.0)
    centrality_factor = 0.5 + (0.5 * min(1.0, parent_centrality))
    return min(1.0, edge.strength * sample_factor * centrality_factor)


def determine_backtest_signal(
    edge_value: float,
    confidence: float,
    settings: BacktestSettings,
) -> str:
    if confidence < settings.min_signal_confidence:
        return "HOLD"
    if edge_value > settings.edge_buy_threshold:
        return "BUY"
    if edge_value < settings.edge_sell_threshold:
        return "SELL"
    return "HOLD"


def load_relationships(
    conn: PgConnection,
    *,
    domains: tuple[str, ...] | None = None,
) -> list[DiscoveredEdge]:
    domain_filter = ""
    params: list[object] = []
    if domains:
        domain_filter = "AND m.domain = ANY(%s)"
        params.append(list(domains))

    query = f"""
        SELECT
            r.parent_market_id,
            r.parent_market,
            r.related_market_id,
            r.related_market,
            r.relationship_type,
            COALESCE(r.strength, 0),
            COALESCE(r.correlation, 0),
            COALESCE(r.beta, 0),
            COALESCE(r.intercept, 0),
            COALESCE(r.conditional_slope, r.beta, 0),
            COALESCE(r.n_observations, 0),
            m.domain
        FROM market_relationships r
        LEFT JOIN markets m ON m.id = r.parent_market_id
        WHERE r.parent_market_id IS NOT NULL
          AND r.related_market_id IS NOT NULL
          AND r.relationship_type LIKE 'discovered_%%'
          {domain_filter}
    """
    with conn.cursor() as cur:
        if params:
            cur.execute(query, tuple(params))
        else:
            cur.execute(query)
        rows = cur.fetchall()

    edges: list[DiscoveredEdge] = []
    for row in rows:
        correlation = float(row[6])
        n_obs = int(row[10])
        correlation_shrunk = correlation
        if n_obs > 0:
            from statistics import shrink_correlation

            correlation_shrunk = shrink_correlation(correlation, n_obs)

        edges.append(
            DiscoveredEdge(
                parent_id=row[0],
                parent_label=row[1],
                child_id=row[2],
                child_label=row[3],
                relationship_type=row[4],
                strength=float(row[5]),
                correlation=correlation,
                correlation_shrunk=correlation_shrunk,
                beta=float(row[7]),
                intercept=float(row[8]),
                conditional_slope=float(row[9]),
                n_observations=n_obs,
            )
        )
    return edges


def _aligned_pair_history(
    history: pd.DataFrame,
    parent_id: str,
    child_id: str,
) -> pd.DataFrame:
    subset = history[history["market_id"].isin([parent_id, child_id])]
    if subset.empty:
        return pd.DataFrame()

    wide = load_price_matrix(subset)
    if parent_id not in wide.columns or child_id not in wide.columns:
        return pd.DataFrame()

    aligned = wide[[parent_id, child_id]].dropna()
    aligned = aligned.rename(columns={parent_id: "parent", child_id: "child"})
    return aligned.reset_index()


def _future_row(
    aligned: pd.DataFrame,
    index: int,
    horizon_minutes: int,
) -> pd.Series | None:
    signal_time = aligned.loc[index, "recorded_at"]
    future = aligned.loc[index + 1 :]
    if future.empty:
        return None

    deadline = signal_time + pd.Timedelta(minutes=horizon_minutes)
    within = future[future["recorded_at"] <= deadline]
    if not within.empty:
        return within.iloc[-1]
    return future.iloc[0]


def _simple_pnl(signal: str, child_t: float, child_t_plus: float) -> float:
    if signal == "BUY":
        return child_t_plus - child_t
    if signal == "SELL":
        return child_t - child_t_plus
    return 0.0


def _directional_win(
    signal: str,
    expected: float,
    child_t: float,
    child_t_plus: float,
    *,
    win_requires_pnl: bool,
) -> bool:
    pnl = _simple_pnl(signal, child_t, child_t_plus)
    if win_requires_pnl:
        return pnl > 0
    if signal == "BUY":
        return child_t_plus > child_t or child_t_plus >= expected
    if signal == "SELL":
        return child_t_plus < child_t or child_t_plus <= expected
    return False


def _append_outcome(
    outcomes: list[BacktestOutcome],
    *,
    edge: DiscoveredEdge,
    domain: str | None,
    signal_time: pd.Timestamp,
    horizon_minutes: int,
    signal: str,
    expected: float,
    child_yes: float,
    child_t_plus: float,
    edge_at_t: float,
    edge_at_t_plus: float,
    confidence: float,
    future_recorded_at: pd.Timestamp,
    settings: BacktestSettings,
    evaluation_mode: EvaluationMode,
) -> None:
    directional_win = _directional_win(
        signal,
        expected,
        child_yes,
        child_t_plus,
        win_requires_pnl=settings.win_requires_pnl,
    )
    outcomes.append(
        BacktestOutcome(
            parent_market_id=edge.parent_id,
            child_market_id=edge.child_id,
            domain=domain,
            signal_time=signal_time,
            horizon_minutes=horizon_minutes,
            signal=signal,
            expected_probability=expected,
            observed_at_t=child_yes,
            observed_at_t_plus=child_t_plus,
            edge_at_t=edge_at_t,
            edge_at_t_plus=edge_at_t_plus,
            confidence=confidence,
            directional_win=directional_win,
            edge_closed=abs(edge_at_t_plus) <= abs(edge_at_t) * BACKTEST_EDGE_CLOSE_FRACTION,
            minutes_to_reprice=(future_recorded_at - signal_time).total_seconds() / 60.0,
            simple_pnl=_simple_pnl(signal, child_yes, child_t_plus),
            evaluation_mode=evaluation_mode,
        )
    )


def walk_forward_pair(
    aligned: pd.DataFrame,
    edge: DiscoveredEdge,
    domain: str | None,
    parent_centrality: float,
    settings: BacktestSettings,
) -> list[BacktestOutcome]:
    outcomes: list[BacktestOutcome] = []

    if len(aligned) <= settings.min_train_snapshots:
        return outcomes

    for index in range(settings.min_train_snapshots, len(aligned)):
        train = aligned.iloc[:index]
        stats = compute_pair_statistics(
            train["parent"],
            train["child"],
            min_observations=settings.min_train_snapshots,
        )
        if stats is None:
            continue
        if stats.n_observations < settings.min_observations:
            continue
        if abs(stats.correlation_shrunk) < settings.correlation_threshold:
            continue
        if stats.strength < settings.min_strength:
            continue

        parent_yes = float(aligned.loc[index, "parent"])
        child_yes = float(aligned.loc[index, "child"])
        expected = expected_from_regression(parent_yes, stats.intercept, stats.beta)
        edge_at_t = expected - child_yes

        virtual_edge = DiscoveredEdge(
            parent_id=edge.parent_id,
            parent_label=edge.parent_label,
            child_id=edge.child_id,
            child_label=edge.child_label,
            relationship_type=edge.relationship_type,
            strength=stats.strength,
            correlation=stats.correlation,
            correlation_shrunk=stats.correlation_shrunk,
            beta=stats.beta,
            intercept=stats.intercept,
            conditional_slope=stats.conditional_slope,
            n_observations=stats.n_observations,
        )
        confidence = compute_confidence(virtual_edge, parent_centrality)
        signal = determine_backtest_signal(edge_at_t, confidence, settings)
        if signal == "HOLD":
            continue

        future = _future_row(aligned, index, settings.horizon_minutes)
        if future is None:
            continue

        child_t_plus = float(future["child"])
        expected_t_plus = expected_from_regression(
            float(future["parent"]), stats.intercept, stats.beta
        )
        edge_at_t_plus = expected_t_plus - child_t_plus
        signal_time = pd.Timestamp(aligned.loc[index, "recorded_at"])

        _append_outcome(
            outcomes,
            edge=edge,
            domain=domain,
            signal_time=signal_time,
            horizon_minutes=settings.horizon_minutes,
            signal=signal,
            expected=expected,
            child_yes=child_yes,
            child_t_plus=child_t_plus,
            edge_at_t=edge_at_t,
            edge_at_t_plus=edge_at_t_plus,
            confidence=confidence,
            future_recorded_at=pd.Timestamp(future["recorded_at"]),
            settings=settings,
            evaluation_mode="walk_forward",
        )

    return outcomes


def replay_with_stored_model(
    aligned: pd.DataFrame,
    edge: DiscoveredEdge,
    domain: str | None,
    parent_centrality: float,
    settings: BacktestSettings,
) -> list[BacktestOutcome]:
    """Replay using stored graph coefficients when walk-forward data is too thin."""
    outcomes: list[BacktestOutcome] = []

    if len(aligned) < 2:
        return outcomes
    if edge.n_observations < settings.min_observations:
        return outcomes

    for index in range(len(aligned) - 1):
        parent_yes = float(aligned.loc[index, "parent"])
        child_yes = float(aligned.loc[index, "child"])
        expected = expected_from_regression(parent_yes, edge.intercept, edge.beta)
        edge_at_t = expected - child_yes
        confidence = compute_confidence(edge, parent_centrality)
        signal = determine_backtest_signal(edge_at_t, confidence, settings)
        if signal == "HOLD":
            continue

        future = _future_row(aligned, index, settings.horizon_minutes)
        if future is None:
            continue

        child_t_plus = float(future["child"])
        expected_t_plus = expected_from_regression(
            float(future["parent"]), edge.intercept, edge.beta
        )
        edge_at_t_plus = expected_t_plus - child_t_plus
        signal_time = pd.Timestamp(aligned.loc[index, "recorded_at"])

        _append_outcome(
            outcomes,
            edge=edge,
            domain=domain,
            signal_time=signal_time,
            horizon_minutes=settings.horizon_minutes,
            signal=signal,
            expected=expected,
            child_yes=child_yes,
            child_t_plus=child_t_plus,
            edge_at_t=edge_at_t,
            edge_at_t_plus=edge_at_t_plus,
            confidence=confidence,
            future_recorded_at=pd.Timestamp(future["recorded_at"]),
            settings=settings,
            evaluation_mode="replay",
        )

    return outcomes


def summarize(outcomes: list[BacktestOutcome]) -> BacktestSummary:
    if not outcomes:
        return BacktestSummary(
            total_evaluations=0,
            actionable_signals=0,
            directional_wins=0,
            edge_closed_count=0,
            directional_win_rate=0.0,
            edge_closed_rate=0.0,
            mean_edge_at_signal=0.0,
            mean_edge_after=0.0,
            mean_minutes_to_reprice=None,
        )

    directional_wins = sum(1 for outcome in outcomes if outcome.directional_win)
    edge_closed = sum(1 for outcome in outcomes if outcome.edge_closed)
    reprices = [
        outcome.minutes_to_reprice
        for outcome in outcomes
        if outcome.minutes_to_reprice is not None
    ]

    return BacktestSummary(
        total_evaluations=len(outcomes),
        actionable_signals=len(outcomes),
        directional_wins=directional_wins,
        edge_closed_count=edge_closed,
        directional_win_rate=directional_wins / len(outcomes),
        edge_closed_rate=edge_closed / len(outcomes),
        mean_edge_at_signal=sum(abs(o.edge_at_t) for o in outcomes) / len(outcomes),
        mean_edge_after=sum(abs(o.edge_at_t_plus) for o in outcomes) / len(outcomes),
        mean_minutes_to_reprice=(sum(reprices) / len(reprices)) if reprices else None,
    )


def summarize_by_domain(outcomes: list[BacktestOutcome]) -> dict[str, BacktestSummary]:
    by_domain: dict[str, list[BacktestOutcome]] = {}
    for outcome in outcomes:
        key = outcome.domain or "unknown"
        by_domain.setdefault(key, []).append(outcome)
    return {domain: summarize(rows) for domain, rows in sorted(by_domain.items())}


def run_backtest(
    edges: list[DiscoveredEdge],
    history: pd.DataFrame,
    centrality: dict[str, float],
    domain_by_parent: dict[str, str | None],
    settings: BacktestSettings | None = None,
) -> tuple[list[BacktestOutcome], BacktestSummary, BacktestDiagnostics]:
    settings = settings or BacktestSettings.from_config()
    if settings.domains:
        domain_set = set(settings.domains)
        edges = [
            edge
            for edge in edges
            if domain_by_parent.get(edge.parent_id) in domain_set
        ]
    all_outcomes: list[BacktestOutcome] = []
    walk_forward_outcomes: list[BacktestOutcome] = []
    replay_outcomes: list[BacktestOutcome] = []
    pairs_with_history = 0
    pairs_walk_forward = 0
    pairs_replay = 0

    for edge in edges:
        aligned = _aligned_pair_history(history, edge.parent_id, edge.child_id)
        if len(aligned) < 2:
            continue

        pairs_with_history += 1
        domain = domain_by_parent.get(edge.parent_id)
        parent_centrality = centrality.get(edge.parent_id, 0.0)

        wf_outcomes: list[BacktestOutcome] = []
        if len(aligned) > settings.min_train_snapshots + 1:
            wf_outcomes = walk_forward_pair(
                aligned,
                edge,
                domain,
                parent_centrality,
                settings,
            )
            if wf_outcomes:
                pairs_walk_forward += 1
                walk_forward_outcomes.extend(wf_outcomes)

        pair_outcomes = list(wf_outcomes)
        if not settings.walk_forward_only and not wf_outcomes:
            rp_outcomes = replay_with_stored_model(
                aligned,
                edge,
                domain,
                parent_centrality,
                settings,
            )
            if rp_outcomes:
                pairs_replay += 1
                replay_outcomes.extend(rp_outcomes)
                pair_outcomes = rp_outcomes

        all_outcomes.extend(pair_outcomes)

    diagnostics = BacktestDiagnostics(
        pairs_evaluated=len(edges),
        pairs_with_history=pairs_with_history,
        pairs_walk_forward=pairs_walk_forward,
        pairs_replay=pairs_replay,
        walk_forward_signals=len(walk_forward_outcomes),
        replay_signals=len(replay_outcomes),
        walk_forward_summary=summarize(walk_forward_outcomes),
        replay_summary=summarize(replay_outcomes),
        domain_summaries=summarize_by_domain(all_outcomes),
    )

    return all_outcomes, summarize(all_outcomes), diagnostics


def settings_to_dict(settings: BacktestSettings) -> dict:
    return {
        "correlation_threshold": settings.correlation_threshold,
        "edge_buy_threshold": settings.edge_buy_threshold,
        "edge_sell_threshold": settings.edge_sell_threshold,
        "min_signal_confidence": settings.min_signal_confidence,
        "min_strength": settings.min_strength,
        "min_train_snapshots": settings.min_train_snapshots,
        "min_observations": settings.min_observations,
        "horizon_minutes": settings.horizon_minutes,
        "walk_forward_only": settings.walk_forward_only,
        "win_requires_pnl": settings.win_requires_pnl,
        "domains": list(settings.domains) if settings.domains else None,
        "hourly_alignment": True,
    }


def save_backtest_run(
    conn: PgConnection,
    outcomes: list[BacktestOutcome],
    summary: BacktestSummary,
    config: dict,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO backtest_runs (
                config_json,
                total_evaluations,
                actionable_signals,
                directional_wins,
                edge_closed_count,
                directional_win_rate,
                edge_closed_rate,
                mean_edge_at_signal,
                mean_edge_after,
                mean_minutes_to_reprice
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                json.dumps(config),
                summary.total_evaluations,
                summary.actionable_signals,
                summary.directional_wins,
                summary.edge_closed_count,
                Decimal(str(summary.directional_win_rate)),
                Decimal(str(summary.edge_closed_rate)),
                Decimal(str(summary.mean_edge_at_signal)),
                Decimal(str(summary.mean_edge_after)),
                Decimal(str(summary.mean_minutes_to_reprice))
                if summary.mean_minutes_to_reprice is not None
                else None,
            ),
        )
        run_id = cur.fetchone()[0]

        for outcome in outcomes:
            cur.execute(
                """
                INSERT INTO backtest_results (
                    run_id,
                    parent_market_id,
                    child_market_id,
                    domain,
                    signal_time,
                    horizon_minutes,
                    signal,
                    expected_probability,
                    observed_at_t,
                    observed_at_t_plus,
                    edge_at_t,
                    edge_at_t_plus,
                    confidence,
                    directional_win,
                    edge_closed,
                    minutes_to_reprice,
                    simple_pnl
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    outcome.parent_market_id,
                    outcome.child_market_id,
                    outcome.domain,
                    outcome.signal_time.to_pydatetime(),
                    outcome.horizon_minutes,
                    outcome.signal,
                    Decimal(str(outcome.expected_probability)),
                    Decimal(str(outcome.observed_at_t)),
                    Decimal(str(outcome.observed_at_t_plus)),
                    Decimal(str(outcome.edge_at_t)),
                    Decimal(str(outcome.edge_at_t_plus)),
                    Decimal(str(outcome.confidence)),
                    outcome.directional_win,
                    outcome.edge_closed,
                    Decimal(str(outcome.minutes_to_reprice))
                    if outcome.minutes_to_reprice is not None
                    else None,
                    Decimal(str(outcome.simple_pnl)),
                ),
            )

    return run_id
