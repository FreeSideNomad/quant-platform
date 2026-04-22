"""Probability of Backtest Overfitting via Combinatorially Symmetric Cross-Validation.

Reference: Bailey, Borwein, López de Prado, Zhu (2014),
'The Probability of Backtest Overfitting', Journal of Computational Finance.

Algorithm (CSCV):
1. Partition the period axis into S equal slices (S even).
2. For every combination of S/2 slices as IS and the complement as OS:
   a. Compute Sharpe per strategy on IS; pick the IS-winner.
   b. Compute the OS rank of that strategy among all strategies.
   c. Logit-transform the rank (pseudo-rank to avoid 0/1 boundary).
3. PBO = fraction of combinations where logit < 0 (i.e. IS-winner ranks
   below median OS).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

import numpy as np


@dataclass(frozen=True)
class PBOScore:
    pbo: float
    n_combinations: int
    median_rank: float
    n_strategies: int


def _annualised_sharpe(returns: np.ndarray, periods_per_year: int) -> np.ndarray:
    """Per-column Sharpe ratio."""
    means = returns.mean(axis=0)
    stds = returns.std(axis=0, ddof=1)
    stds = np.where(stds == 0, np.nan, stds)
    return means / stds * math.sqrt(periods_per_year)


def pbo(
    returns: np.ndarray,
    *,
    n_partitions: int = 16,
    sharpe_periods_per_year: int = 252,
) -> PBOScore:
    """CSCV-PBO on a (T, N) returns matrix.

    Args:
        returns: shape (n_periods, n_strategies).
        n_partitions: must be even; higher = more combinations,
            lower variance, more compute.
        sharpe_periods_per_year: annualisation factor.

    Returns:
        PBOScore. PBO is in [0, 1]; lower = less overfit; > 0.5 is
        a strong red flag.
    """
    if n_partitions % 2 != 0:
        raise ValueError("n_partitions must be even (CSCV requirement)")
    n_periods, n_strategies = returns.shape
    if n_periods < n_partitions * 2:
        raise ValueError(
            f"insufficient periods: have {n_periods}, "
            f"need at least {n_partitions * 2}"
        )

    slice_size = n_periods // n_partitions
    boundaries = [i * slice_size for i in range(n_partitions + 1)]
    boundaries[-1] = n_periods

    slices = [
        returns[boundaries[i] : boundaries[i + 1]] for i in range(n_partitions)
    ]

    half = n_partitions // 2
    logits: list[float] = []
    for is_choice in combinations(range(n_partitions), half):
        os_choice = tuple(i for i in range(n_partitions) if i not in is_choice)

        is_returns = np.vstack([slices[i] for i in is_choice])
        os_returns = np.vstack([slices[i] for i in os_choice])

        is_sharpe = _annualised_sharpe(is_returns, sharpe_periods_per_year)
        os_sharpe = _annualised_sharpe(os_returns, sharpe_periods_per_year)

        if np.all(np.isnan(is_sharpe)):
            continue

        is_winner = int(np.nanargmax(is_sharpe))
        os_rank = (
            np.sum(os_sharpe < os_sharpe[is_winner]) + 0.5 * np.sum(os_sharpe == os_sharpe[is_winner])
        ) / n_strategies
        os_rank = min(max(os_rank, 1e-6), 1 - 1e-6)
        logits.append(math.log(os_rank / (1 - os_rank)))

    logits_arr = np.array(logits)
    pbo_value = float(np.mean(logits_arr < 0))

    return PBOScore(
        pbo=pbo_value,
        n_combinations=len(logits),
        median_rank=float(np.median([1 / (1 + math.exp(-x)) for x in logits])),
        n_strategies=n_strategies,
    )
