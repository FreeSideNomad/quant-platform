"""Deflated Sharpe Ratio unit tests.

Reference: Bailey & López de Prado (2014), 'The Deflated Sharpe Ratio'.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.quant.validation.dsr import deflated_sharpe


@pytest.mark.unit
def test_dsr_pinches_sharpe_when_many_trials():
    """A Sharpe of 2.0 from 1 trial deflates to a high-confidence score;
    the same Sharpe from 100 trials deflates much lower."""
    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.005, 252)

    single_trial = deflated_sharpe(returns, num_trials=1, trials_sharpe_var=None)
    many_trials = deflated_sharpe(returns, num_trials=100, trials_sharpe_var=0.5)

    assert single_trial.deflated > many_trials.deflated
    assert 0.0 <= single_trial.probability <= 1.0
    assert 0.0 <= many_trials.probability <= 1.0


@pytest.mark.unit
def test_dsr_passes_for_high_sharpe_low_skew():
    rng = np.random.default_rng(42)
    returns = rng.normal(0.003, 0.01, 1260)  # 5y daily, Sharpe ~ 4

    score = deflated_sharpe(returns, num_trials=1, trials_sharpe_var=None)
    assert score.observed_sharpe > 3.0
    assert score.probability > 0.95


@pytest.mark.unit
def test_dsr_handles_zero_variance():
    returns = np.zeros(100)
    score = deflated_sharpe(returns, num_trials=1, trials_sharpe_var=None)
    assert score.observed_sharpe == 0.0
    assert score.deflated == 0.0


@pytest.mark.unit
def test_dsr_rejects_too_few_observations():
    with pytest.raises(ValueError, match="insufficient"):
        deflated_sharpe(np.array([0.01, -0.01]), num_trials=1, trials_sharpe_var=None)
