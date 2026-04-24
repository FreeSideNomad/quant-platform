"""Math-grounded reference-value tests for PBO and DSR.

The archive-ported unit tests check directional/bounds properties (e.g.
`deflated_single > deflated_many`, `0.3 <= pbo <= 0.7`). Those are
necessary but not sufficient for the milestone DoD ("math signed off").

The tests in this file cross-check the module's outputs against
independent re-implementations of the published formulas:

- DSR: Bailey & López de Prado (2014) "The Deflated Sharpe Ratio",
  recomputed here using scipy primitives (skew, kurtosis, norm.cdf).
- PBO: Bailey/Borwein/López de Prado/Zhu (2014) "The Probability of
  Backtest Overfitting", verified at algorithmically-derivable edge
  cases (one strategy dominates every slice → PBO = 0 exactly;
  strategies perfectly anti-correlated IS↔OS → PBO = 1 exactly).

Implementation notes on DSR formula:
- The module uses scipy's default bias=True skewness and fisher=False
  (Pearson) kurtosis, where normal = 3. The deflator formula is:
    deflator_arg = (1 - g3*sr_raw + (g4-1)/4 * sr_raw^2) / (n-1)
  where g4 is Pearson kurtosis (normal=3), g3 is biased skewness.
- This reduces to the t-stat form:
    t = sr_raw * sqrt(n-1) / sqrt(1 - g3*sr_raw + (g4-1)/4 * sr_raw^2)
  which the tests use for clarity.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import kurtosis, norm, skew

from quantplatform.validation.dsr import deflated_sharpe
from quantplatform.validation.pbo import pbo


# ---------- DSR: Bailey 2014 formula cross-check ----------


def test_dsr_matches_bailey_formula_at_num_trials_one() -> None:
    """With num_trials=1, E[max_SR]=0 so the deflated t-statistic reduces to
    the raw Sharpe corrected only for non-normality (Bailey 2014 Eq. 7 with
    expected-max term = 0). Recompute the expected probability here using
    scipy primitives and assert deflated_sharpe() matches to 1e-10.

    The module computes:
        g3 = skew(returns)                # bias=True (scipy default)
        g4 = kurtosis(returns, fisher=False)  # Pearson kurtosis (normal=3)
        deflator_arg = (1 - g3*sr_raw + (g4-1)/4 * sr_raw^2) / (n-1)
        deflated = observed / (sqrt(deflator_arg) * sqrt(periods_per_year))

    Which simplifies to:
        t = sr_raw * sqrt(n-1) / sqrt(1 - g3*sr_raw + (g4-1)/4 * sr_raw^2)
    """
    rng = np.random.default_rng(seed=42)
    n = 252
    returns = rng.normal(loc=0.001, scale=0.005, size=n)

    # Independent reimplementation matching the module's exact formula:
    sigma = float(returns.std(ddof=1))
    sr_raw = float(returns.mean() / sigma)   # per-period Sharpe
    g3 = float(skew(returns))                # bias=True to match module
    g4 = float(kurtosis(returns, fisher=False))  # Pearson kurtosis (normal=3) per Bailey 2014 Eq. 7

    numer = 1.0 - g3 * sr_raw + ((g4 - 1.0) / 4.0) * sr_raw ** 2
    assert numer > 0.0, "deflator numerator must be positive for this fixture"
    t_stat = sr_raw * math.sqrt(n - 1) / math.sqrt(numer)
    expected_probability = float(norm.cdf(t_stat))

    score = deflated_sharpe(returns, num_trials=1, trials_sharpe_var=None)

    assert math.isclose(score.probability, expected_probability, abs_tol=1e-10), (
        f"DSR probability {score.probability} != scipy-reference {expected_probability}"
    )


def test_dsr_matches_bailey_formula_with_multiple_trials() -> None:
    """With num_trials>1, Bailey's expected-max-Sharpe term kicks in.

    The module's _expected_max_sharpe returns an annualised threshold using
    the Euler-gamma/exp-quantile approximation:
        e_max = sqrt(var) * ((1-euler)*ppf(1-1/T) + euler*ppf(1-1/(T*e)))

    The deflated t-statistic is then:
        deflated = (observed_annual - e_max) / (sqrt(deflator_arg) * sqrt(252))

    This test reimplements that formula with scipy and asserts agreement to 1e-10.
    """
    rng = np.random.default_rng(seed=7)
    n = 1260  # 5y daily
    returns = rng.normal(loc=0.0015, scale=0.01, size=n)
    num_trials = 50
    trials_var = 1.0

    sigma = float(returns.std(ddof=1))
    sr_raw = float(returns.mean() / sigma)
    observed_annual = sr_raw * math.sqrt(252)
    g3 = float(skew(returns))                # bias=True to match module
    g4 = float(kurtosis(returns, fisher=False))  # Pearson kurtosis (normal=3) per Bailey 2014 Eq. 7

    # Bailey-de Prado expected max Sharpe under multiple testing (annualised):
    euler = 0.5772156649
    q = float(norm.ppf(1.0 - 1.0 / num_trials))
    q_inv = float(norm.ppf(1.0 - 1.0 / (num_trials * math.e)))
    e_max_annual = math.sqrt(trials_var) * ((1.0 - euler) * q + euler * q_inv)

    deflator_arg = (1.0 - g3 * sr_raw + ((g4 - 1.0) / 4.0) * sr_raw ** 2) / (n - 1)
    assert deflator_arg > 0.0, "deflator_arg must be positive for this fixture"
    deflated = (observed_annual - e_max_annual) / (math.sqrt(deflator_arg) * math.sqrt(252))
    expected_probability = float(norm.cdf(deflated))

    score = deflated_sharpe(
        returns,
        num_trials=num_trials,
        trials_sharpe_var=trials_var,
        periods_per_year=252,
    )

    assert math.isclose(score.probability, expected_probability, abs_tol=1e-10), (
        f"DSR multi-trial probability {score.probability} != "
        f"scipy-reference {expected_probability}"
    )


# ---------- PBO: algorithmically-derivable edge cases ----------


def test_pbo_is_zero_when_one_strategy_dominates_every_slice() -> None:
    """If strategy 0 has a huge constant edge over every other strategy in
    every partition of the periods, then:
      - For every IS subset, strategy 0 has the highest in-sample Sharpe.
      - For every OS subset, strategy 0 also has the highest OS Sharpe.
      - Therefore the IS-winner is the OS-winner in every combination.
      - The logit of the OS-rank is positive for every combination.
      - Fraction of combinations with logit < 0 → 0 → PBO = 0.0 exactly.

    This is a semantic check on the CSCV algorithm — it directly tests what
    "PBO" is supposed to mean, independent of sampling noise.
    """
    rng = np.random.default_rng(seed=0)
    n_periods, n_strategies = 64, 5
    returns = rng.normal(loc=0.0, scale=0.001, size=(n_periods, n_strategies))
    # Give strategy 0 an absurdly large constant edge (1000x the noise scale)
    # so it dominates every slice regardless of partitioning.
    returns[:, 0] += 1.0

    score = pbo(returns, n_partitions=8, sharpe_periods_per_year=252)
    assert score.pbo == 0.0, f"expected PBO=0 under total domination, got {score.pbo}"


def test_pbo_is_one_when_in_sample_winner_always_becomes_os_worst() -> None:
    """Construct a returns matrix that perfectly anti-correlates in-sample and
    out-of-sample winners.

    Strategy k has return +edge on periods in slice k (its "home" slice) and
    -edge everywhere else. With n_partitions=4 and n_strategies=4 (one strategy
    per home slice) and small noise to prevent zero-std Sharpe:

      - For every IS combination of 2 slices, the IS winner is the strategy
        whose home slice appears in the IS set and who gets elected by argmax.
      - On the complementary OS slices, the elected IS winner has -edge on
        both OS slices → worst or near-worst OS Sharpe.
      - The fraction of combinations with logit(OS-rank) < 0 → 1.0.

    Verified numerically for the specific seed/scale used here.
    """
    n_partitions = 4
    n_strategies = n_partitions  # one strategy per home slice
    slice_size = 16
    n_periods = n_partitions * slice_size
    edge = 0.1
    rng = np.random.default_rng(seed=0)
    # Small noise (0.1% of edge) so Sharpe is well-defined but not so large
    # it overwhelms the edge signal.
    noise = rng.normal(0.0, edge * 0.01, (n_periods, n_strategies))
    returns = np.full((n_periods, n_strategies), -edge) + noise
    for s in range(n_strategies):
        start = s * slice_size
        end = (s + 1) * slice_size
        returns[start:end, s] = edge + noise[start:end, s]

    score = pbo(returns, n_partitions=n_partitions, sharpe_periods_per_year=252)
    assert score.pbo == 1.0, (
        f"expected PBO=1 under perfect IS↔OS anti-correlation, got {score.pbo}"
    )
