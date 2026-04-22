"""PBO unit tests.

Reference: Bailey, Borwein, López de Prado, Zhu (2014),
'The Probability of Backtest Overfitting'.

We construct synthetic strategy-vs-period return matrices with known
overfitting properties and check that pbo() reports the expected
range. We do NOT test floating-point exactness — PBO is an empirical
estimator with sampling noise even on synthetic data.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.quant.validation.pbo import pbo


@pytest.mark.unit
def test_pbo_returns_low_for_genuinely_uncorrelated_winner():
    """If the in-sample winner is consistently the OOS winner, PBO is low."""
    rng = np.random.default_rng(seed=42)
    n_periods, n_strategies = 200, 20

    base_signal = rng.normal(0.001, 0.005, n_periods)
    returns = np.tile(base_signal[:, None], (1, n_strategies))
    returns += rng.normal(0, 0.001, (n_periods, n_strategies))
    returns[:, 5] += 0.0005

    score = pbo(returns, n_partitions=8, sharpe_periods_per_year=252)
    assert 0.0 <= score.pbo <= 1.0
    assert score.pbo < 0.4


@pytest.mark.unit
def test_pbo_returns_high_for_pure_noise_strategy_universe():
    """If every strategy is independent noise, in-sample best has no edge OOS — PBO ~ 0.5."""
    rng = np.random.default_rng(seed=42)
    returns = rng.normal(0, 0.01, (200, 20))

    score = pbo(returns, n_partitions=8, sharpe_periods_per_year=252)
    assert 0.0 <= score.pbo <= 1.0
    assert 0.3 <= score.pbo <= 0.7


@pytest.mark.unit
def test_pbo_rejects_too_few_periods():
    rng = np.random.default_rng(seed=42)
    returns = rng.normal(0, 0.01, (10, 20))
    with pytest.raises(ValueError, match="insufficient periods"):
        pbo(returns, n_partitions=8, sharpe_periods_per_year=252)


@pytest.mark.unit
def test_pbo_rejects_odd_partition_count():
    rng = np.random.default_rng(seed=42)
    returns = rng.normal(0, 0.01, (200, 20))
    with pytest.raises(ValueError, match="even"):
        pbo(returns, n_partitions=7, sharpe_periods_per_year=252)
