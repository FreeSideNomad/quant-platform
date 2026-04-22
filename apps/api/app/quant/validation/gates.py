"""Promotion-gate evaluation.

A model version may transition draft → production only if it passes
all gates. The gates are tenant-configurable (defaults shown).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateThresholds:
    pbo_max: float = 0.7
    dsr_probability_min: float = 0.95
    walk_forward_min_folds: int = 8


@dataclass(frozen=True)
class GateResults:
    pbo: float | None
    dsr_probability: float | None
    walk_forward_fold_count: int | None
    pbo_pass: bool
    dsr_pass: bool
    walk_forward_pass: bool

    @property
    def all_pass(self) -> bool:
        return self.pbo_pass and self.dsr_pass and self.walk_forward_pass


def evaluate_gates(
    *,
    pbo: float | None,
    dsr_probability: float | None,
    walk_forward_fold_count: int | None,
    thresholds: GateThresholds | None = None,
) -> GateResults:
    th = thresholds or GateThresholds()
    pbo_pass = pbo is not None and pbo <= th.pbo_max
    dsr_pass = dsr_probability is not None and dsr_probability >= th.dsr_probability_min
    wf_pass = (
        walk_forward_fold_count is not None
        and walk_forward_fold_count >= th.walk_forward_min_folds
    )
    return GateResults(
        pbo=pbo,
        dsr_probability=dsr_probability,
        walk_forward_fold_count=walk_forward_fold_count,
        pbo_pass=pbo_pass,
        dsr_pass=dsr_pass,
        walk_forward_pass=wf_pass,
    )
