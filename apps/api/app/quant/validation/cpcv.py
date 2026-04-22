"""Combinatorial Purged Cross-Validation.

Reference: López de Prado, AFML, Ch. 12. CPCV addresses two financial
specifics standard k-fold CV does not:
- **Combinatorial paths**: for N splits with k test splits, generate
  C(N, k) test combinations rather than just N folds. Average across
  paths to estimate OOS performance more robustly.
- **Embargo**: drop training observations for `embargo_periods`
  immediately after each test window to prevent leakage from
  serially-correlated returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class CPCVConfig:
    n_splits: int  # total number of splits (e.g. 6)
    n_test_splits: int  # how many splits per test combination (e.g. 2)
    embargo_periods: int  # contiguous periods to purge after each test window

    def __post_init__(self) -> None:
        if self.n_test_splits >= self.n_splits:
            raise ValueError(
                f"n_test_splits ({self.n_test_splits}) must be < n_splits ({self.n_splits})"
            )
        if self.n_test_splits < 1:
            raise ValueError("n_test_splits must be >= 1")
        if self.embargo_periods < 0:
            raise ValueError("embargo_periods must be >= 0")


def cpcv_splits(
    *, n_observations: int, cfg: CPCVConfig
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Generate (train_indices, test_indices) for every CPCV combination."""
    if n_observations < cfg.n_splits:
        raise ValueError(
            f"n_observations ({n_observations}) < n_splits ({cfg.n_splits})"
        )

    split_size = n_observations // cfg.n_splits
    boundaries = [i * split_size for i in range(cfg.n_splits + 1)]
    boundaries[-1] = n_observations

    split_ranges = [
        np.arange(boundaries[i], boundaries[i + 1]) for i in range(cfg.n_splits)
    ]

    for test_choice in combinations(range(cfg.n_splits), cfg.n_test_splits):
        test_idx = np.concatenate([split_ranges[i] for i in test_choice])

        purged: set[int] = set()
        if cfg.embargo_periods > 0:
            for ti in test_idx:
                purged.update(range(int(ti) + 1, int(ti) + 1 + cfg.embargo_periods))

        train_idx = np.array(
            [
                i
                for i in range(n_observations)
                if i not in test_idx.tolist() and i not in purged
            ]
        )
        yield train_idx, test_idx
