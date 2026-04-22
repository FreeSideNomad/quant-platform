"""Demo / smoke jobs for the quant platform code location."""

from __future__ import annotations

from dagster import define_asset_job

from app.dagster_defs.assets.bronze import bronze_synthetic_universe
from app.dagster_defs.assets.gold import gold_alpha_features
from app.dagster_defs.assets.silver import silver_pit_prices
from app.dagster_defs.assets.walk_forward import walk_forward_fold_results

demo_full_lineage = define_asset_job(
    name="demo_full_lineage",
    selection=[
        bronze_synthetic_universe,
        silver_pit_prices,
        gold_alpha_features,
        walk_forward_fold_results,
    ],
    description=(
        "End-to-end materialisation for the demo: bronze -> silver -> gold "
        "-> walk_forward_fold_results. Persists rows to features_gold, "
        "daily_prices_silver, and walk_forward_folds. The demo seed script "
        "wraps this with the strategy-registration + promotion + inference "
        "steps that are not (yet) Dagster assets."
    ),
)

__all__ = ["demo_full_lineage"]
