"""Dagster code location for the quant platform.

Registers the bronze → silver → gold data-layer assets, their asset checks,
and the walk-forward fold results asset.
"""

from __future__ import annotations

from dagster import Definitions

from app.dagster_defs.assets import (
    bronze_synthetic_universe,
    gold_alpha_features,
    gold_row_count_check,
    pit_integrity_check,
    silver_pit_prices,
)
from app.dagster_defs.assets.walk_forward import walk_forward_fold_results
from app.dagster_defs.jobs import demo_full_lineage

defs = Definitions(
    assets=[
        bronze_synthetic_universe,
        silver_pit_prices,
        gold_alpha_features,
        walk_forward_fold_results,
    ],
    asset_checks=[pit_integrity_check, gold_row_count_check],
    jobs=[demo_full_lineage],
    schedules=[],
    sensors=[],
)

__all__ = ["defs"]
