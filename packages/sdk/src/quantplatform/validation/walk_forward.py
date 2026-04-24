"""Walk-forward window arithmetic.

Pure functions: given a configuration and a (data_start, data_end)
range, emit a sequence of (train_start, train_end, test_start, test_end)
folds that advance through time without leakage.

Quarter is treated as a 90-day approximation (calendar quarters
vary 89-92 days; 90 is a convenient round value that aligns Apr 1
to Jan 1 + 90 etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator, Literal

Step = Literal["week", "month", "quarter"]
_STEP_DAYS = {"week": 7, "month": 30, "quarter": 90}
_WINDOW_PATTERN = re.compile(r"^(\d+)([dwmqy])$")


def _parse_window(spec: str) -> int:
    m = _WINDOW_PATTERN.match(spec)
    if not m:
        raise ValueError(f"unknown window spec: {spec!r}")
    n, unit = int(m.group(1)), m.group(2)
    days = {"d": 1, "w": 7, "m": 30, "q": 90, "y": 365}[unit]
    return n * days


@dataclass(frozen=True)
class WalkForwardConfig:
    step: Step
    train_window: str
    test_window: str
    min_folds: int

    def __post_init__(self) -> None:
        if self.step not in _STEP_DAYS:
            raise ValueError(f"unknown step: {self.step!r}")
        if self.min_folds < 1:
            raise ValueError("min_folds must be >= 1")
        _parse_window(self.train_window)
        _parse_window(self.test_window)


@dataclass(frozen=True)
class Fold:
    index: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date


def fold_dates(
    cfg: WalkForwardConfig, *, data_start: date, data_end: date
) -> Iterator[Fold]:
    """Yield non-overlapping walk-forward folds within [data_start, data_end].

    Each fold advances by cfg.step.  Stops when test_end would exceed data_end.
    Raises ValueError if the number of produced folds is below cfg.min_folds.
    """
    train_days = _parse_window(cfg.train_window)
    test_days = _parse_window(cfg.test_window)
    step_days = _STEP_DAYS[cfg.step]

    folds: list[Fold] = []
    k = 0
    while True:
        train_start = data_start + timedelta(days=k * step_days)
        train_end = train_start + timedelta(days=train_days)
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=test_days - 1)
        if test_end > data_end:
            break
        folds.append(
            Fold(
                index=k,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        k += 1

    if len(folds) < cfg.min_folds:
        raise ValueError(
            f"insufficient data: produced {len(folds)} folds, "
            f"need at least {cfg.min_folds}"
        )

    yield from folds
