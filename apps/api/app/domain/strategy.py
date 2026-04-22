"""Strategy aggregate — represents a quant's submitted strategy spec."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FeatureColumnSpec:
    source: str
    name: str


@dataclass(frozen=True)
class FeatureSetSpec:
    name: str
    universe: str
    sources: dict[str, str]
    columns: list[FeatureColumnSpec]
    target: FeatureColumnSpec


@dataclass(frozen=True)
class WalkForwardSpec:
    step: str
    train_window: str
    test_window: str
    min_folds: int


@dataclass(frozen=True)
class BacktestSpec:
    cost_model: str
    capacity_aum_usd: float
    benchmark: str


@dataclass(frozen=True)
class StrategySpec:
    feature_set: FeatureSetSpec
    model_class: str
    strategy_class: str
    walk_forward: WalkForwardSpec
    backtest: BacktestSpec
    serving_schedule: str | None = None
    hyperparameter_space: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StrategySpec":
        fs = raw["feature_set"]
        return cls(
            feature_set=FeatureSetSpec(
                name=fs["name"],
                universe=fs["universe"],
                sources=fs["sources"],
                columns=[FeatureColumnSpec(**c) for c in fs["columns"]],
                target=FeatureColumnSpec(**fs["target"]),
            ),
            model_class=raw["model_class"],
            strategy_class=raw["strategy_class"],
            walk_forward=WalkForwardSpec(**raw["walk_forward"]),
            backtest=BacktestSpec(**raw["backtest"]),
            serving_schedule=raw.get("serving_schedule"),
            hyperparameter_space=raw.get("hyperparameter_space"),
        )

    def canonical_json(self) -> str:
        def _to_dict(obj: Any) -> Any:
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
            if isinstance(obj, list):
                return [_to_dict(v) for v in obj]
            if isinstance(obj, dict):
                return {k: _to_dict(v) for k, v in obj.items()}
            return obj

        return json.dumps(_to_dict(self), sort_keys=True, separators=(",", ":"))

    def spec_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RegisterStrategyResult:
    strategy_id: str
    family: str
    created: bool  # True if newly inserted; False if no-op replay


def new_strategy_id() -> str:
    """Module-level helper for testability (mock in tests)."""
    return str(uuid.uuid4())
