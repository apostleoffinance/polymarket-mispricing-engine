"""Statistical estimators for edge discovery and pricing."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import (
    CORRELATION_SHRINKAGE_K,
    LEAD_LAG_MAX_HOURS,
    MIN_OVERLAPPING_SNAPSHOTS,
    STABILITY_MIN_WINDOWS,
    STABILITY_ROLLING_WINDOW,
)


@dataclass(frozen=True)
class PairStatistics:
    correlation: float
    correlation_shrunk: float
    beta: float
    intercept: float
    conditional_slope: float
    strength: float
    n_observations: int
    lag_minutes: int = 0
    lead_correlation: float = 0.0
    stability_score: float = 0.0


def shrink_correlation(correlation: float, n_observations: int) -> float:
    if n_observations <= 0:
        return 0.0
    weight = math.sqrt(n_observations / (n_observations + CORRELATION_SHRINKAGE_K))
    return correlation * weight


def composite_strength(
    beta: float,
    correlation_shrunk: float,
    n_observations: int,
    *,
    stability_score: float = 1.0,
) -> float:
    sample_weight = math.sqrt(n_observations / (n_observations + 10))
    stability_weight = 0.5 + (0.5 * max(0.0, min(1.0, stability_score)))
    return min(
        1.0,
        abs(beta) * sample_weight * abs(correlation_shrunk) * stability_weight,
    )


def compute_lead_lag(
    parent: pd.Series,
    child: pd.Series,
    *,
    max_lag_hours: int = LEAD_LAG_MAX_HOURS,
    min_observations: int | None = None,
) -> tuple[int, float]:
    """
    Best lag in hours where positive lag means parent leads child.

    Correlates parent[t] with child[t + lag].
    """
    required = min_observations if min_observations is not None else MIN_OVERLAPPING_SNAPSHOTS
    aligned = pd.concat([parent, child], axis=1, join="inner").dropna()
    if len(aligned) < required:
        return 0, 0.0

    parent_values = aligned.iloc[:, 0].astype(float)
    child_values = aligned.iloc[:, 1].astype(float)
    best_lag = 0
    best_corr = float(parent_values.corr(child_values))
    if np.isnan(best_corr):
        best_corr = 0.0

    for lag in range(-max_lag_hours, max_lag_hours + 1):
        if lag == 0:
            continue
        shifted_child = child_values.shift(-lag)
        pair = pd.concat([parent_values, shifted_child], axis=1).dropna()
        if len(pair) < required:
            continue
        corr = float(pair.iloc[:, 0].corr(pair.iloc[:, 1]))
        if np.isnan(corr):
            continue
        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag

    return best_lag, best_corr


def compute_stability(
    parent: pd.Series,
    child: pd.Series,
    *,
    window: int = STABILITY_ROLLING_WINDOW,
    min_windows: int = STABILITY_MIN_WINDOWS,
) -> float:
    """
    Fraction of rolling windows that keep the same correlation sign as the
    full-sample correlation, weighted by mean |rolling corr|.
    """
    aligned = pd.concat([parent, child], axis=1, join="inner").dropna()
    if len(aligned) < window + min_windows:
        return 0.0

    parent_values = aligned.iloc[:, 0].astype(float)
    child_values = aligned.iloc[:, 1].astype(float)
    overall = float(parent_values.corr(child_values))
    if np.isnan(overall) or overall == 0.0:
        return 0.0

    rolling = parent_values.rolling(window).corr(child_values).dropna()
    if len(rolling) < min_windows:
        return 0.0

    overall_sign = 1.0 if overall > 0 else -1.0
    same_sign = float((np.sign(rolling) == overall_sign).mean())
    mean_abs = float(np.abs(rolling).mean())
    return max(0.0, min(1.0, same_sign * min(1.0, mean_abs / 0.5)))


def compute_pair_statistics(
    parent: pd.Series,
    child: pd.Series,
    *,
    min_observations: int | None = None,
    include_dynamics: bool = True,
) -> PairStatistics | None:
    """OLS child ~ parent on aligned, non-null observations."""
    required = min_observations if min_observations is not None else MIN_OVERLAPPING_SNAPSHOTS
    aligned = pd.concat([parent, child], axis=1, join="inner").dropna()
    n_observations = len(aligned)
    if n_observations < required:
        return None

    parent_values = aligned.iloc[:, 0].astype(float)
    child_values = aligned.iloc[:, 1].astype(float)

    if parent_values.nunique() < 2 or child_values.nunique() < 2:
        return None

    correlation = float(parent_values.corr(child_values))
    if np.isnan(correlation):
        return None

    correlation_shrunk = shrink_correlation(correlation, n_observations)
    beta, intercept = np.polyfit(parent_values, child_values, 1)
    beta = float(beta)
    intercept = float(intercept)

    lag_hours = 0
    lead_correlation = correlation
    stability_score = 1.0
    if include_dynamics:
        lag_hours, lead_correlation = compute_lead_lag(
            parent_values,
            child_values,
            min_observations=required,
        )
        stability_score = compute_stability(parent_values, child_values)

    strength = composite_strength(
        beta,
        correlation_shrunk,
        n_observations,
        stability_score=stability_score,
    )

    return PairStatistics(
        correlation=correlation,
        correlation_shrunk=correlation_shrunk,
        beta=beta,
        intercept=intercept,
        conditional_slope=beta,
        strength=strength,
        n_observations=n_observations,
        lag_minutes=int(lag_hours * 60),
        lead_correlation=float(lead_correlation),
        stability_score=float(stability_score),
    )


def expected_from_regression(
    parent_yes: float,
    intercept: float,
    beta: float,
) -> float:
    """E[child | parent] from rolling OLS coefficients."""
    return max(0.0, min(1.0, intercept + beta * parent_yes))
