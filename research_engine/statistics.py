"""Statistical estimators for edge discovery and pricing."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import CORRELATION_SHRINKAGE_K, MIN_OVERLAPPING_SNAPSHOTS


@dataclass(frozen=True)
class PairStatistics:
    correlation: float
    correlation_shrunk: float
    beta: float
    intercept: float
    conditional_slope: float
    strength: float
    n_observations: int


def shrink_correlation(correlation: float, n_observations: int) -> float:
    if n_observations <= 0:
        return 0.0
    weight = math.sqrt(n_observations / (n_observations + CORRELATION_SHRINKAGE_K))
    return correlation * weight


def composite_strength(
    beta: float,
    correlation_shrunk: float,
    n_observations: int,
) -> float:
    sample_weight = math.sqrt(n_observations / (n_observations + 10))
    return min(1.0, abs(beta) * sample_weight * abs(correlation_shrunk))


def compute_pair_statistics(
    parent: pd.Series,
    child: pd.Series,
    *,
    min_observations: int | None = None,
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
    strength = composite_strength(beta, correlation_shrunk, n_observations)

    return PairStatistics(
        correlation=correlation,
        correlation_shrunk=correlation_shrunk,
        beta=beta,
        intercept=intercept,
        conditional_slope=beta,
        strength=strength,
        n_observations=n_observations,
    )


def expected_from_regression(
    parent_yes: float,
    intercept: float,
    beta: float,
) -> float:
    """E[child | parent] from rolling OLS coefficients."""
    return max(0.0, min(1.0, intercept + beta * parent_yes))
