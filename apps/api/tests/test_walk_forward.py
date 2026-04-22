"""Tests for walk-forward window arithmetic.

Pure-Python, no DB / docker needed.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.quant.walk_forward import Fold, WalkForwardConfig, fold_dates


@pytest.mark.unit
def test_quarter_step_3y_train_1q_test_produces_expected_fold_dates() -> None:
    cfg = WalkForwardConfig(
        step="quarter",
        train_window="3y",
        test_window="1q",
        min_folds=1,
    )
    folds = list(fold_dates(cfg, data_start=date(2018, 1, 1), data_end=date(2023, 12, 31)))

    first = folds[0]
    assert first.train_start == date(2018, 1, 1)
    assert first.train_end == date(2020, 12, 31)
    assert first.test_start == date(2021, 1, 1)
    assert first.test_end == date(2021, 3, 31)

    second = folds[1]
    assert second.train_start == date(2018, 4, 1)
    assert second.test_start == date(2021, 4, 1)


@pytest.mark.unit
def test_min_folds_check_raises_when_data_too_short() -> None:
    cfg = WalkForwardConfig(
        step="quarter",
        train_window="3y",
        test_window="1q",
        min_folds=10,
    )
    with pytest.raises(ValueError, match="insufficient data"):
        list(fold_dates(cfg, data_start=date(2020, 1, 1), data_end=date(2021, 12, 31)))


@pytest.mark.unit
def test_month_step_2y_train_1m_test() -> None:
    cfg = WalkForwardConfig(
        step="month",
        train_window="2y",
        test_window="1m",
        min_folds=1,
    )
    folds = list(fold_dates(cfg, data_start=date(2020, 1, 1), data_end=date(2023, 12, 31)))

    assert len(folds) >= 1
    first = folds[0]
    # train: 2*365 = 730 days; train_end = 2020-01-01 + 729 = 2021-12-31
    assert first.train_start == date(2020, 1, 1)
    assert first.train_end == date(2021, 12, 31)
    # test: 1*30 = 30 days; test_start = 2022-01-01; test_end = 2022-01-30
    assert first.test_start == date(2022, 1, 1)
    assert first.test_end == date(2022, 1, 30)

    second = folds[1]
    # second train_start = 2020-01-01 + 30 = 2020-01-31
    assert second.train_start == date(2020, 1, 31)


@pytest.mark.unit
def test_unknown_step_raises() -> None:
    with pytest.raises(ValueError, match="unknown step"):
        WalkForwardConfig(
            step="fortnight",  # type: ignore[arg-type]
            train_window="1y",
            test_window="1m",
            min_folds=1,
        )


@pytest.mark.unit
def test_fold_does_not_overlap_with_train() -> None:
    cfg = WalkForwardConfig(
        step="week",
        train_window="1y",
        test_window="1m",
        min_folds=1,
    )
    folds = list(fold_dates(cfg, data_start=date(2020, 1, 1), data_end=date(2022, 12, 31)))

    for fold in folds:
        # test window must start strictly after train window ends
        assert fold.test_start > fold.train_end
        # test window must end on or after test start
        assert fold.test_end >= fold.test_start
        # train start must precede train end
        assert fold.train_start <= fold.train_end
