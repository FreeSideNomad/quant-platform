"""López de Prado honesty checks: PBO, DSR, CPCV + walk-forward harness.

Reference:
- López de Prado, *Advances in Financial Machine Learning*, Wiley 2018, Ch. 11–13.
- Bailey & López de Prado, 'The Probability of Backtest Overfitting', JCF 2014.
- Bailey & López de Prado, 'The Deflated Sharpe Ratio', JoPM 2014.

Pure functions only. Nothing in this package imports MLflow, SQLAlchemy,
FastAPI, or any platform service — the gate math must be testable in
isolation and re-usable from both the SDK and the server role.
"""

from __future__ import annotations

__all__ = [
    "PBOScore",
    "pbo",
    "DSRScore",
    "deflated_sharpe",
    "CPCVConfig",
    "CPCVSplit",
    "cpcv_splits",
    "WalkForwardConfig",
    "Fold",
    "fold_dates",
    "GateThresholds",
    "GateResults",
    "evaluate_gates",
]

from quantplatform.validation.cpcv import CPCVConfig, CPCVSplit, cpcv_splits
from quantplatform.validation.dsr import DSRScore, deflated_sharpe
from quantplatform.validation.gates import GateResults, GateThresholds, evaluate_gates
from quantplatform.validation.pbo import PBOScore, pbo
from quantplatform.validation.walk_forward import Fold, WalkForwardConfig, fold_dates
