"""CPCV unit tests.

Reference: López de Prado, *Advances in Financial Machine Learning*
(Wiley 2018), Ch. 12.
"""

from __future__ import annotations

import numpy as np
import pytest

from quantplatform.validation.cpcv import cpcv_splits, CPCVConfig


@pytest.mark.unit
def test_cpcv_emits_expected_number_of_paths():
    """CPCV(N=6, k=2) emits C(6, 2) = 15 (train, test) splits."""
    cfg = CPCVConfig(n_splits=6, n_test_splits=2, embargo_periods=0)
    splits = list(cpcv_splits(n_observations=600, cfg=cfg))
    assert len(splits) == 15


@pytest.mark.unit
def test_cpcv_train_and_test_indices_are_disjoint():
    cfg = CPCVConfig(n_splits=6, n_test_splits=2, embargo_periods=5)
    for train_idx, test_idx in cpcv_splits(n_observations=600, cfg=cfg):
        assert len(set(train_idx) & set(test_idx)) == 0


@pytest.mark.unit
def test_cpcv_embargo_purges_periods_after_test_window():
    """An embargo of 5 means train indices skip the 5 periods immediately after each test window."""
    cfg = CPCVConfig(n_splits=4, n_test_splits=1, embargo_periods=5)
    splits = list(cpcv_splits(n_observations=400, cfg=cfg))
    train_idx, test_idx = splits[0]
    test_end = max(test_idx)
    purged_zone = set(range(test_end + 1, test_end + 6))
    assert not (set(train_idx) & purged_zone)


@pytest.mark.unit
def test_cpcv_rejects_more_test_splits_than_total():
    with pytest.raises(ValueError, match="n_test_splits"):
        CPCVConfig(n_splits=4, n_test_splits=5, embargo_periods=0)
