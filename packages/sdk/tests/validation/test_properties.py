"""Property-based tests for validation math.

Hypothesis-driven invariants that any implementation must satisfy,
independently of specific reference examples (which live in the other
test files). Kept deliberately conservative on shape so CI stays fast.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
from hypothesis import assume, given, settings, strategies as st

from quantplatform.validation.cpcv import CPCVConfig, cpcv_splits
from quantplatform.validation.dsr import deflated_sharpe
from quantplatform.validation.pbo import pbo
from quantplatform.validation.walk_forward import WalkForwardConfig, fold_dates


# ---------- PBO ----------

@settings(max_examples=25, deadline=None)
@given(
    n_periods=st.integers(min_value=32, max_value=64),
    n_strategies=st.integers(min_value=3, max_value=6),
    seed=st.integers(min_value=0, max_value=2**31 - 1),
)
def test_pbo_is_in_unit_interval(n_periods: int, n_strategies: int, seed: int) -> None:
    """PBO ∈ [0, 1] for any returns matrix — the logit-rank fraction is bounded."""
    rng = np.random.default_rng(seed)
    # n_partitions=4: C(4, 2) = 6 combinations, all combinations require periods
    # divisible by 4 for clean partitioning.
    n_partitions = 4
    periods = (n_periods // n_partitions) * n_partitions
    assume(periods >= n_partitions * 2)  # at least 2 periods per slice
    returns = rng.normal(size=(periods, n_strategies))
    score = pbo(returns, n_partitions=n_partitions, sharpe_periods_per_year=252)
    assert 0.0 <= score.pbo <= 1.0
    assert score.n_combinations > 0


# ---------- DSR ----------

@settings(max_examples=25, deadline=None)
@given(
    sharpe=st.floats(min_value=-2.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    n_obs=st.integers(min_value=60, max_value=500),
    num_trials=st.integers(min_value=1, max_value=200),
)
def test_dsr_probability_is_in_unit_interval(
    sharpe: float, n_obs: int, num_trials: int
) -> None:
    """deflated_sharpe.probability ∈ [0, 1] for realistic parameters."""
    rng = np.random.default_rng(0)
    # Synthesize a returns series with roughly the target sharpe ratio.
    returns = rng.normal(loc=sharpe / np.sqrt(252.0), scale=1.0 / np.sqrt(252.0), size=n_obs)
    score = deflated_sharpe(
        returns,
        periods_per_year=252,
        num_trials=num_trials,
        trials_sharpe_var=1.0,
    )
    assert 0.0 <= score.probability <= 1.0


@settings(max_examples=20, deadline=None)
@given(
    sharpe=st.floats(min_value=0.5, max_value=3.0, allow_nan=False),
    n_obs=st.integers(min_value=120, max_value=360),
)
def test_dsr_more_trials_never_raises_probability(sharpe: float, n_obs: int) -> None:
    """Monotonicity: at equal everything-else, more trials → p-value never increases."""
    rng = np.random.default_rng(0)
    returns = rng.normal(loc=sharpe / np.sqrt(252.0), scale=1.0 / np.sqrt(252.0), size=n_obs)
    p_few = deflated_sharpe(
        returns, periods_per_year=252, num_trials=1, trials_sharpe_var=1.0
    ).probability
    p_many = deflated_sharpe(
        returns, periods_per_year=252, num_trials=100, trials_sharpe_var=1.0
    ).probability
    assert p_many <= p_few + 1e-9  # monotone non-increasing, slack for float noise


# ---------- CPCV ----------

@settings(max_examples=30, deadline=None)
@given(
    n_observations=st.integers(min_value=40, max_value=120),
    n_splits=st.integers(min_value=4, max_value=8),
    n_test_splits=st.integers(min_value=1, max_value=3),
    embargo=st.integers(min_value=0, max_value=3),
)
def test_cpcv_train_and_test_are_always_disjoint(
    n_observations: int, n_splits: int, n_test_splits: int, embargo: int
) -> None:
    """train_idx ∩ test_idx = ∅ for any valid CPCV config, and indices stay in range."""
    assume(n_test_splits < n_splits)
    cfg = CPCVConfig(n_splits=n_splits, n_test_splits=n_test_splits, embargo_periods=embargo)
    for train_idx, test_idx in cpcv_splits(n_observations=n_observations, cfg=cfg):
        assert set(train_idx.tolist()).isdisjoint(set(test_idx.tolist()))
        all_idx = set(train_idx.tolist()) | set(test_idx.tolist())
        assert all(0 <= int(i) < n_observations for i in all_idx)


# ---------- Walk-forward ----------

@settings(max_examples=25, deadline=None)
@given(
    seed=st.integers(min_value=0, max_value=2**31 - 1),
    data_days=st.integers(min_value=500, max_value=2000),
)
def test_walk_forward_folds_never_leak(seed: int, data_days: int) -> None:
    """train_end < test_start in every fold — no leakage between train and test."""
    cfg = WalkForwardConfig(
        step="month",
        train_window="365d",
        test_window="30d",
        min_folds=1,
    )
    start = date(2020, 1, 1)
    end = start + timedelta(days=data_days)
    folds = list(fold_dates(cfg, data_start=start, data_end=end))
    for f in folds:
        assert f.train_end < f.test_start
        assert f.test_start <= f.test_end
    # Silence unused-seed warning — seed is part of the Hypothesis strategy shape
    # even though the walk-forward logic is deterministic given inputs.
    _ = seed
