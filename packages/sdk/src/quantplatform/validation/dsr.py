# apps/api/app/quant/validation/dsr.py
"""Deflated Sharpe Ratio.

Reference: Bailey & López de Prado (2014), 'The Deflated Sharpe Ratio'.

Adjusts the observed Sharpe ratio for:
- Sample size (more periods = lower variance of the estimator)
- Skewness and kurtosis of returns
- Number of trials run before this strategy was selected
- Variance across trial Sharpes (if known)

Returns the deflated Sharpe and the implied probability that the
true Sharpe exceeds zero, given the multiple-testing context.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm, skew, kurtosis


@dataclass(frozen=True)
class DSRScore:
    observed_sharpe: float
    deflated: float  # Same units as Sharpe.
    probability: float  # P(true Sharpe > 0 | observed evidence).
    n_observations: int


def _expected_max_sharpe(num_trials: int, trials_var: float) -> float:
    """Bailey-de Prado expected maximum Sharpe under multiple testing."""
    if num_trials <= 1 or trials_var <= 0:
        return 0.0
    euler = 0.5772156649
    quantile = norm.ppf(1 - 1.0 / num_trials)
    quantile_inv = norm.ppf(1 - 1.0 / (num_trials * math.e))
    expected_max = math.sqrt(trials_var) * (
        (1 - euler) * quantile + euler * quantile_inv
    )
    return float(expected_max)


def deflated_sharpe(
    returns: np.ndarray,
    *,
    num_trials: int = 1,
    trials_sharpe_var: float | None = None,
    periods_per_year: int = 252,
) -> DSRScore:
    """Compute the deflated Sharpe ratio and the implied probability.

    Args:
        returns: 1-D array of strategy returns at uniform frequency.
        num_trials: Number of strategies tested before selecting this
            one (the multiple-testing burden).
        trials_sharpe_var: Variance of the Sharpe ratios across the
            tested strategies. If None and num_trials > 1, defaults
            to 1.0 (a conservative assumption).
        periods_per_year: Annualisation factor (252 for daily, 52 for
            weekly, 12 for monthly).
    """
    if len(returns) < 5:
        raise ValueError("insufficient observations: need at least 5")

    sigma = float(returns.std(ddof=1))
    if sigma == 0:
        return DSRScore(observed_sharpe=0.0, deflated=0.0, probability=0.5, n_observations=len(returns))

    # Per-period Sharpe (used in the Bailey-LdP deflator formula).
    sr_raw = float(returns.mean() / sigma)
    # Annualised Sharpe (stored in DSRScore and used as the threshold comparison).
    observed = sr_raw * math.sqrt(periods_per_year)
    n = len(returns)
    g3 = float(skew(returns))
    g4 = float(kurtosis(returns, fisher=False))  # Pearson kurtosis (normal=3) per Bailey 2014 Eq. 7

    if num_trials > 1:
        var = trials_sharpe_var if trials_sharpe_var is not None else 1.0
        sr_threshold = _expected_max_sharpe(num_trials, var)
    else:
        sr_threshold = 0.0

    # Deflator uses per-period SR so the expression stays in (0, 1] range.
    deflator_arg = (1 - g3 * sr_raw + ((g4 - 1) / 4) * sr_raw**2) / (n - 1)
    if deflator_arg <= 0 or math.isnan(deflator_arg):
        deflated = observed
    else:
        deflator = math.sqrt(deflator_arg) * math.sqrt(periods_per_year)
        deflated = (observed - sr_threshold) / deflator

    probability = float(norm.cdf(deflated))

    return DSRScore(
        observed_sharpe=observed,
        deflated=deflated,
        probability=probability,
        n_observations=n,
    )
