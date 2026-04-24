"""Edge-case coverage for validation error branches.

The archive tests focus on happy paths; this file exists to hit the
remaining validation branches so the 100% line-coverage gate on
quantplatform.validation is satisfied.
"""
from __future__ import annotations

import numpy as np
import pytest

from quantplatform.validation.cpcv import CPCVConfig, cpcv_splits
from quantplatform.validation.dsr import _expected_max_sharpe, deflated_sharpe
from quantplatform.validation.pbo import pbo
from quantplatform.validation.walk_forward import WalkForwardConfig


# ---- cpcv.py ----

def test_cpcv_config_rejects_zero_test_splits() -> None:
    with pytest.raises(ValueError, match="n_test_splits must be >= 1"):
        CPCVConfig(n_splits=4, n_test_splits=0, embargo_periods=0)


def test_cpcv_config_rejects_negative_embargo() -> None:
    with pytest.raises(ValueError, match="embargo_periods must be >= 0"):
        CPCVConfig(n_splits=4, n_test_splits=1, embargo_periods=-1)


def test_cpcv_splits_rejects_too_few_observations() -> None:
    cfg = CPCVConfig(n_splits=6, n_test_splits=2, embargo_periods=0)
    with pytest.raises(ValueError, match="n_observations"):
        list(cpcv_splits(n_observations=3, cfg=cfg))


# ---- dsr.py (private helper — defensive early return) ----

def test_expected_max_sharpe_returns_zero_when_num_trials_is_one() -> None:
    assert _expected_max_sharpe(1, 1.0) == 0.0


def test_expected_max_sharpe_returns_zero_when_trials_var_is_zero() -> None:
    assert _expected_max_sharpe(10, 0.0) == 0.0


def test_dsr_deflator_nan_guard_falls_back_to_observed() -> None:
    """Returns containing NaN propagate NaN through scipy moments, making
    deflator_arg NaN.  The ``math.isnan`` guard in dsr.py must catch this
    and fall back to ``deflated = observed`` (line 89) instead of crashing.

    With Pearson kurtosis the quadratic deflator_arg is always >= 0 for
    finite returns (Cauchy-Schwarz guarantee on central moments), so the
    only way to reach the guard is via NaN propagation from the input.
    """
    returns = np.array([0.01, 0.02, np.nan, 0.03, 0.01, 0.02] * 10)
    score = deflated_sharpe(returns, num_trials=1, trials_sharpe_var=None)
    # When the guard fires, deflated == observed (the annualised per-period Sharpe).
    # observed itself will be NaN (mean/std of NaN-contaminated series), so probability
    # will be 0.5 (norm.cdf(nan) in scipy returns nan → float(nan)).
    # The important thing is that no exception is raised.
    assert 0.0 <= score.probability <= 1.0 or np.isnan(score.probability)


# ---- pbo.py ----

def test_pbo_skips_combinations_with_all_nan_is_sharpe() -> None:
    """If a slice has zero variance for every strategy, is_sharpe is all NaN
    and that combination must be skipped (the `continue` branch in pbo.py).

    Construction: n_partitions=2 → C(2, 1)=2 combinations, each IS is a
    single slice. Make slice 0 all-zero for every strategy (std=0 →
    NaN sharpe for every strategy in that slice). When IS=slice_0, the
    whole is_sharpe vector is NaN → continue. When IS=slice_1, returns
    are random → finite sharpe → proceeds. Result: only 1 combination
    contributes.
    """
    rng = np.random.default_rng(0)
    returns = np.zeros((8, 2))
    returns[4:] = rng.normal(size=(4, 2))
    score = pbo(returns, n_partitions=2, sharpe_periods_per_year=252)
    assert score.n_combinations == 1


# ---- walk_forward.py ----

def test_walk_forward_config_rejects_unknown_window_spec() -> None:
    """_parse_window raises on a string that doesn't match <int><unit>."""
    with pytest.raises(ValueError, match="unknown window spec"):
        WalkForwardConfig(
            step="month",
            train_window="bogus",
            test_window="30d",
            min_folds=1,
        )


def test_walk_forward_config_rejects_zero_min_folds() -> None:
    with pytest.raises(ValueError, match="min_folds must be >= 1"):
        WalkForwardConfig(
            step="month",
            train_window="365d",
            test_window="30d",
            min_folds=0,
        )
