"""Unit tests for evaluate_gates — state table coverage."""
from __future__ import annotations

import pytest

from quantplatform.validation.gates import (
    GateResults,
    GateThresholds,
    evaluate_gates,
)


def test_default_thresholds_match_spec() -> None:
    t = GateThresholds()
    assert t.pbo_max == 0.7
    assert t.dsr_probability_min == 0.95
    assert t.walk_forward_min_folds == 8


def test_all_pass_when_metrics_meet_thresholds() -> None:
    result = evaluate_gates(pbo=0.3, dsr_probability=0.98, walk_forward_fold_count=10)
    assert result.pbo_pass is True
    assert result.dsr_pass is True
    assert result.walk_forward_pass is True
    assert result.all_pass is True


def test_pbo_fails_above_threshold() -> None:
    result = evaluate_gates(pbo=0.8, dsr_probability=0.98, walk_forward_fold_count=10)
    assert result.pbo_pass is False
    assert result.all_pass is False


def test_dsr_fails_below_threshold() -> None:
    result = evaluate_gates(pbo=0.3, dsr_probability=0.5, walk_forward_fold_count=10)
    assert result.dsr_pass is False
    assert result.all_pass is False


def test_walk_forward_fails_below_min_folds() -> None:
    result = evaluate_gates(pbo=0.3, dsr_probability=0.98, walk_forward_fold_count=4)
    assert result.walk_forward_pass is False
    assert result.all_pass is False


def test_missing_metric_fails_that_gate() -> None:
    result = evaluate_gates(pbo=None, dsr_probability=0.98, walk_forward_fold_count=10)
    assert result.pbo_pass is False
    assert result.all_pass is False


def test_custom_thresholds_override_defaults() -> None:
    thresh = GateThresholds(pbo_max=0.5, dsr_probability_min=0.9, walk_forward_min_folds=4)
    result = evaluate_gates(
        pbo=0.4,
        dsr_probability=0.92,
        walk_forward_fold_count=5,
        thresholds=thresh,
    )
    assert result.all_pass is True


def test_boundary_values_are_inclusive() -> None:
    # pbo exactly equal to max → pass; dsr exactly equal to min → pass;
    # folds exactly equal to min → pass.
    result = evaluate_gates(pbo=0.7, dsr_probability=0.95, walk_forward_fold_count=8)
    assert result.all_pass is True


def test_gate_results_is_immutable() -> None:
    result = evaluate_gates(pbo=0.3, dsr_probability=0.98, walk_forward_fold_count=10)
    with pytest.raises(Exception):  # frozen dataclass raises FrozenInstanceError
        result.pbo_pass = False  # type: ignore[misc]
