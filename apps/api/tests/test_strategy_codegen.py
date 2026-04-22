"""The codegen helper renders syntactically-valid Dagster asset modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.dagster_defs.strategy_codegen import _slugify, write_strategy_asset_file
from app.domain.strategy import StrategySpec


SAMPLE = StrategySpec.from_dict({
    "feature_set": {
        "name": "csi300_alpha158_v1",
        "universe": "csi300_top_constituents",
        "sources": {"alpha158": "gold.csi300_alpha158"},
        "columns": [{"source": "alpha158", "name": "*"}],
        "target": {"source": "alpha158", "name": "label_return_5d"},
    },
    "model_class": "x.Y",
    "strategy_class": "x.Z",
    "walk_forward": {"step": "quarter", "train_window": "3y", "test_window": "1q", "min_folds": 8},
    "backtest": {"cost_model": "almgren_chriss", "capacity_aum_usd": 1.0, "benchmark": "CSI300"},
})


@pytest.mark.unit
def test_slugify_handles_dots_and_dashes():
    assert _slugify("us.equity-long_short") == "us_equity_long_short"


@pytest.mark.unit
def test_codegen_emits_parseable_python(tmp_path: Path):
    out = write_strategy_asset_file(
        strategy_id="abc123",
        family="csi300_long_short_alpha158",
        spec=SAMPLE,
        spec_hash="hashvalue",
        target_dir=tmp_path,
    )
    rendered = out.read_text()
    ast.parse(rendered)  # raises SyntaxError if invalid


@pytest.mark.unit
def test_codegen_idempotent_on_same_family(tmp_path: Path):
    write_strategy_asset_file(
        strategy_id="id1", family="f", spec=SAMPLE, spec_hash="h1", target_dir=tmp_path,
    )
    write_strategy_asset_file(
        strategy_id="id2", family="f", spec=SAMPLE, spec_hash="h2", target_dir=tmp_path,
    )
    files = list(tmp_path.glob("*.py"))
    assert len(files) == 1  # second write overwrites
    assert "id2" in files[0].read_text()
