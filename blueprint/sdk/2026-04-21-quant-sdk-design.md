---
title: Quant Platform Python SDK — Design Specification
date: 2026-04-21
status: draft (v1 contract)
audience: platform engineering team (implementers); quant engineers at customer funds (consumers); architecture review (sign-off)
purpose: >
  The formal contract a quant implements to publish a strategy onto the Quant Platform.
  Defines the five core abstractions (FeatureSet, Model, Strategy, WalkForwardConfig, BacktestConfig),
  the single wiring step (register), the CLI surface, the end-to-end lifecycle, and the integration
  points with MLflow, Polars, the medallion gold layer, PGMQ, Cloud Run Jobs, Vertex AI Custom
  Training, and Dagster. The spec describes the contract, not the implementation; the SDK code is
  a separate work stream.
related:
  - blueprint/positioning/2026-04-21-positioning.md
  - blueprint/prd/2026-04-21-quant-platform-v1.md
  - blueprint/research/2026-04-21-modern-quant-synthesis.md
  - blueprint/src/02-key-ideas.md (Key Idea 7 — research-to-production parity)
  - blueprint/src/07-application.md (worker roles)
  - blueprint/src/08-data-platform.md (medallion gold layer; bi-temporal columns)
  - blueprint/src/09-ml-platform.md (MLflow registry; pyfunc discipline)
  - blueprint/src/14.5-comparison-to-alternatives.md
---

# Quant Platform Python SDK — Design Specification

The platform's value proposition is that a quant ships a model from notebook to audited production without an engineering hand-off. The Python SDK is the surface area on which that proposition is paid out. It is the contract a quant writes against — a small set of base classes, configuration objects, and a single wiring function — and it is the contract the platform reads via Python introspection to validate the strategy, dispatch its training, run its walk-forward evaluation, compute its honesty checks, register its artefacts, gate its promotion, and run its serving schedule.

This spec is the formal description of that contract. It is not the SDK's source code. The implementation is a separate work stream, scoped after this spec is approved. The reader who finishes this document should be able to (a) write a strategy file by hand against the API described here, (b) explain what the platform will do with that file end-to-end, and (c) point to the chapter of the underlying blueprint that justifies each design decision.

The audience is split. For a quant engineer at a customer fund, the SDK is the only platform code they ever import; everything below the import boundary is the platform's problem. For the platform engineering team, the SDK is a public API with stricter compatibility constraints than internal modules and a longer deprecation cycle when it changes. For an architecture reviewer, the SDK is the place where the abstract bets of the blueprint (key ideas 1, 4, 7 — silo tenancy, Postgres-centric, research-to-production parity) become a concrete user-facing artefact. The spec is written to satisfy all three.

The eight ground-truth design decisions on which the spec rests are stated in §1.3 and are not relitigated below. Where this spec discovers a question that was not anticipated by those decisions, it is flagged as **Open question for human decision** and collected in §12.

---

## 1. Goals and Non-Goals

### 1.1 What the SDK is for

The SDK is the *only* surface a quant ever interacts with on the platform's compute side. The quant writes a single Python file (or, more often, a small package of related files) that:

- Declares one or more **feature sets** built from the medallion gold layer (Chapter 8 §Gold).
- Defines one or more **models** as Python classes, each with a `train` method and a `predict` callable.
- Defines one or more **strategies** as Python classes that turn predictions into target positions.
- Declares the **walk-forward** and **backtest** configurations the platform will use to validate the strategy.
- Declares the **resources** each class needs at training time and at serving time.
- Calls `register()` once per strategy to wire the pieces together.

Submitting that file (`quant submit my_strategy.py`) is the entire act of getting a strategy onto the platform. Everything else — dataset extraction, training-fold dispatch to Cloud Run Jobs or Vertex AI Custom Training, walk-forward evaluation, PBO/DSR computation, MLflow registry entries, promotion gating, lazy-reload of the serving role, scheduled inference, audit-log entries — is the platform's responsibility, triggered by what the SDK reports about the file.

The SDK is therefore the **wire format** between the quant and the platform. It is *Python as a configuration language*, not a configuration file pretending to be Python. The platform reads classes via `inspect`; the platform reads instances of Pydantic v2 config models; the platform calls the user's methods at training, walk-forward, backtest, and serving time. The same `predict()` callable is used in all four contexts.

### 1.2 What the SDK is not for

The SDK is not a notebook environment, not a backtest library, not a charting toolkit, not a portfolio optimiser, not a broker integration, not a data-ingestion contract layer. Each of these has a clear home elsewhere in the platform:

- Notebook authoring lives in the platform's embedded Marimo (or Jupyter-Lab fallback) per PRD §3.3 Beat 3. The SDK is what the notebook *imports*; it is not the editor.
- Backtest execution is performed by the `worker-backtest` role (Chapter 7 §Single image, multiple roles; PRD §4.2 T1.1) using a Polars-based engine that wraps vectorbt. The SDK declares the backtest configuration; the engine consumes it.
- Charts are produced by the React frontend (PRD §4.3) from the structured backtest result aggregate. The SDK does not draw.
- Portfolio optimisation libraries (cvxpy, PyPortfolioOpt, custom HRP) are *imported by the user's Strategy class*. The SDK does not bundle them.
- Broker integration is explicitly out of scope for v1 (decision 8 below; see §10).
- Data-ingestion contracts are described in Chapter 8 §File contracts. The SDK *consumes* gold-layer data via FeatureSet declarations; it does not specify how raw data arrives.

The SDK's scope is deliberately narrow. The right test of whether something belongs in the SDK is: *does the quant write it as part of describing a strategy?* If yes, it belongs in the SDK. If no — even if the platform needs it — it belongs elsewhere.

### 1.3 The eight ground-truth design decisions

These decisions are settled. The remainder of this spec assumes them. Any apparent contradiction with these decisions is a bug in this spec, not a deferred design question.

1. **Class-based, not config-file-based.** A Python class is the natural unit of an ML model and an investment strategy: it has hyperparameters as `__init__` arguments, fitted state as instance attributes, and behaviour as methods. A YAML config that calls a Python class via a string reference is the wrong abstraction; it duplicates the class signature in YAML and creates a parallel registry of strings. The platform reads the user's classes directly via `inspect`.

2. **Same `predict()` callable in training, walk-forward, backtest, and serving.** This is the operational form of Key Idea 7 (research-to-production parity). There is one method, defined once on the Model class. The training loop calls it on validation data; the walk-forward harness calls it on each out-of-sample fold; the backtest engine calls it inside the simulation loop; the serving role calls it on each scheduled inference. The same Python function across all four contexts. Train-serve skew is closed by construction.

3. **Polars DataFrames as the lingua franca.** Every method that takes or returns tabular data takes or returns a `pl.DataFrame` or `pl.Series`. Not pandas. Not NumPy arrays. Not Arrow tables. Not custom dataclasses. The platform's data layer is Polars-native (Chapter 8 §Silver, §Gold). The SDK matches.

4. **Strategy as a separate class from Model.** Predictions and positions are different concerns. A Model produces a prediction (what does the data say about future return?); a Strategy produces a target position (given the prediction, the universe, and current positions, what do we want to hold?). The two evolve at different cadences — many strategies share one model; one strategy may ensemble multiple models — and they are validated by different criteria. Coupling them in one class is a category error.

5. **`register()` is the only wiring step.** No imports of platform internals. No decorators that secretly mutate global state. No config files that the SDK reads from disk. The user's strategy file calls `register(...)` exactly once at module top level; that call is the entire handoff to the platform. The platform's submission CLI imports the file, observes the `register()` call, validates the resulting registration, and persists it.

6. **Resources declared per-class, not per-job.** A Model has `resources_train` and `resources_serve` class attributes; a Strategy may have its own `resources_serve`. The platform translates these declarations into Cloud Run Jobs allocations, Vertex AI Custom Training shape requests, and Cloud Run service sizing. The user does not write Kubernetes YAML. The user does not write Cloud Run service definitions. The user writes `Resources(cpu=8, memory_gb=32, gpu=None)`.

7. **Hyperparameter search is opt-in.** If the `hyperparameter_space` argument to `register()` is omitted, the platform trains the model exactly once per fold using the constructor defaults (or the explicit parameters the user provided). If `hyperparameter_space` is present, the platform runs Optuna with the declared distributions. Search is an explicit user choice, not an implicit default.

8. **No broker integration in v1.** Target positions produced by the Strategy are written to a structured file in GCS (or the customer's bucket) and announced via an event on the audit trail. The customer's OMS (order management system) consumes the file. The SDK does not know about broker FIX endpoints, REST APIs, or execution algorithms beyond the Almgren-Chriss model used for backtest cost estimation. Broker integration is a Phase-3 concern.

### 1.4 Non-goals (explicit)

- **Multi-language support.** Python only. Customers writing in R, Scala, or Julia are out of scope; the SDK does not provide language bridges. The MLflow `pyfunc` boundary is the only artefact format.
- **Backwards-compatibility with non-SDK-built models.** A model already trained outside the SDK (e.g., a legacy LightGBM `pkl` file from the customer's existing stack) cannot be promoted onto the platform without being re-expressed as a Model subclass. The migration path is described in §11.
- **Notebook-as-source-of-truth.** A `.ipynb` file is not a deployable artefact. The notebook is a draft of the strategy file; the strategy file is what the platform consumes. Per PRD §3.3 Beat 3, the notebook environment imports the same `features/` and `strategies/` modules as production.
- **Custom DataFrame engines.** Polars only. A Pandas user can convert at the boundary (`pl.from_pandas`); Pandas is not supported as a first-class type in the SDK signatures.
- **Real-time / sub-second serving.** The serving model is request-response with daily-or-faster scheduled inference (PRD §3.2). Tick-level execution is out of scope for v1 (Chapter 9 §High-throughput or GPU-bound serving).

---

## 2. The Five Core Abstractions

The SDK has five user-facing abstractions. Three of them (`FeatureSet`, `WalkForwardConfig`, `BacktestConfig`, plus `FeatureColumn` and `Resources` as auxiliary types) are Pydantic v2 models — declarative, validated at construction time, immutable, JSON-serialisable. Two of them (`Model`, `Strategy`) are abstract base classes the user subclasses.

This section gives the API surface in full. Subsequent sections describe what `register()` does with these classes, how the CLI exposes them, and how the lifecycle plays out.

### 2.1 FeatureSet

#### 2.1.1 Purpose

A `FeatureSet` declares the input vocabulary of a Model. It identifies which gold-layer tables the model reads, which columns from those tables it consumes, what the prediction target is, and over what universe the model operates. The platform reads the FeatureSet to know how to extract training data, how to extract validation data at walk-forward fold boundaries, and how to extract feature vectors at serving time.

The FeatureSet is the integration boundary between the medallion data platform (Chapter 8) and the modelling code. A change in a gold-layer table's schema is detectable as a FeatureSet validation failure; a feature renamed in gold without a matching SDK update fails fast at submission time.

#### 2.1.2 API

```python
from quantplatform import FeatureSet, FeatureColumn

features = FeatureSet(
    name="us_equity_alpha158_v1",
    universe="us_equity_top_1000",
    sources={
        "alpha158": "gold.us_equity_alpha158",
        "fundamentals": "gold.us_equity_fundamentals",
    },
    columns=[
        FeatureColumn("alpha158", "*"),
        FeatureColumn("fundamentals", "log_market_cap"),
        FeatureColumn("fundamentals", "book_to_market"),
    ],
    target=FeatureColumn("alpha158", "label_return_5d"),
)
```

#### 2.1.3 Type signature

`FeatureSet` is a Pydantic v2 `BaseModel` with the following fields:

| Field | Type | Required | Semantics |
| :--- | :--- | :--- | :--- |
| `name` | `str` | yes | Stable identifier; matches `^[a-z][a-z0-9_]*$`; namespaced per tenant; used as the MLflow experiment name suffix and as the directory name in artefact storage. Versioned by `_v{n}` suffix convention (the platform does not interpret the suffix; it is a user convention for human readability). |
| `universe` | `str` | yes | Identifier of a gold-layer universe definition (e.g., `us_equity_top_1000`, `csi_300`, `eu_equity_stoxx600`). The platform resolves this to a list of asset identifiers as-of the extraction `as_of`. Universes themselves are configured at the tenant level (Chapter 8 §Gold) and are not the SDK's concern. |
| `sources` | `dict[str, str]` | yes | A mapping of local alias → fully-qualified gold-layer table name. The alias is what `FeatureColumn` references; the FQN is what the platform queries. The convention `gold.<table_name>` is used; a future cross-tenant data-share story may extend the namespace. |
| `columns` | `list[FeatureColumn]` | yes | The columns the model consumes. The wildcard `"*"` is a valid column name and means "all columns from this source not otherwise reserved." Reserved columns (`_knowable_at`, `_valid_from`, `_valid_to`, the asset and date identifiers) are excluded from the wildcard but added back automatically by the extraction layer. |
| `target` | `FeatureColumn` | yes | The supervised target. Must reference a column in one of the declared sources. The target is excluded from the feature matrix passed to `train()` and `predict()`; it is supplied as a separate argument or as a column with the reserved name `_target` depending on the method (see §2.2.4). |
| `entity_columns` | `list[str]` | no, default `["asset_id", "date"]` | The columns that identify a row uniquely in the cross-section. For cross-sectional equity, `("asset_id", "date")`. For a single time series (a Nixtla-style univariate forecast), `("date",)`. The platform uses this to perform the as-of joins between sources. |
| `as_of_filter` | `bool` | no, default `True` | When True, every extraction filters by `_knowable_at <= :as_of`. Setting this to False is allowed but logged as a warning and surfaces in the audit trail; non-as-of-filtered training is the look-ahead-bias failure mode the bi-temporal schema exists to prevent (Key Idea 8). |

`FeatureColumn` is a small Pydantic v2 model:

```python
class FeatureColumn(BaseModel):
    source: str             # alias matching a key in FeatureSet.sources
    column: str             # column name; "*" is wildcard for the source
```

It also accepts positional construction: `FeatureColumn("alpha158", "log_volume")` is equivalent to `FeatureColumn(source="alpha158", column="log_volume")`.

#### 2.1.4 Semantics

The platform reads a `FeatureSet` declaration and produces a *Polars LazyFrame* over the joined sources, filtered by `_knowable_at <= :as_of` (when `as_of_filter=True`), restricted to the `universe` resolved as-of the same timestamp, with the entity columns and the target column included. This LazyFrame is what gets materialised and passed to `Model.train(train, val)` after a train/validation split.

At serving time, the same FeatureSet is materialised at the inference `as_of` (typically `now() - 1 second` rounded to the serving cadence) and passed to `Model.predict(features)`. The `target` column is omitted at serving (predictions on the target's own values would be label leakage in a cross-sectional context, and there is no target at the inference horizon for a forecast).

The platform validates a `FeatureSet` at submission time by issuing a `LIMIT 1` query against the gold layer with the declared sources, columns, and entity columns. If a column does not exist, a source is not a valid gold table, or the entity columns are missing from a source, submission fails with a structured error pointing at the offending field. This is the schema-drift defence: a feature renamed in gold without a matching SDK update fails before any compute is dispatched.

Wildcards (`FeatureColumn("alpha158", "*")`) are expanded at extraction time, not at submission time. This means a new column added to `gold.us_equity_alpha158` will be picked up automatically on the next training run, which is usually but not always what the user wants. A future v2 may add an `expected_columns` declaration that pins the wildcard expansion at submission time; this is **Open question 2** (§12).

#### 2.1.5 Worked example

A NeuralForecast-style univariate forecast on a single macro series (the 10-year US Treasury yield):

```python
ust10y_features = FeatureSet(
    name="ust10y_forecast_v1",
    universe="ust_yield_curve",
    sources={
        "yields": "gold.us_treasury_yield_curve",
        "macro": "gold.macro_indicators_us",
    },
    columns=[
        FeatureColumn("yields", "yield_10y"),
        FeatureColumn("macro", "cpi_yoy"),
        FeatureColumn("macro", "fed_funds_rate"),
    ],
    target=FeatureColumn("yields", "yield_10y_future_5d"),
    entity_columns=["date"],
)
```

Note the `entity_columns=["date"]` indicating a single-series, time-only entity space — this signals to the platform that the model consumes a time series rather than a cross-section, and the walk-forward harness will use a contiguous time-based split rather than a CPCV-style purged split (see §2.4.4).

### 2.2 Model

#### 2.2.1 Purpose

A `Model` is the user's training-and-prediction code, packaged as a Python class. It is the SDK's smallest unit of trained-state ownership. One Model class produces one MLflow registered model; one MLflow registered model has one production version at a time, with a version history.

The Model class is *the* place where the research-to-production parity discipline (Key Idea 7) lives. There is exactly one `predict()` method; it is called identically at training-validation, walk-forward, backtest, and serving time. The platform does not provide a separate "production wrapper" the user has to maintain in lockstep.

#### 2.2.2 API

```python
from quantplatform import Model, Resources, FeatureSet
import polars as pl
import lightgbm as lgb

class AlphaModel(Model):
    feature_set = features                                 # class attribute; FeatureSet instance
    resources_train = Resources(cpu=8, memory_gb=32)
    resources_serve = Resources(cpu=2, memory_gb=4)

    def __init__(self, learning_rate: float = 0.05, num_leaves: int = 64):
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self._lgb: lgb.Booster | None = None

    def train(self, train: pl.DataFrame, val: pl.DataFrame) -> None:
        ...

    def predict(self, features: pl.DataFrame) -> pl.Series:
        ...
```

#### 2.2.3 Required class attributes

| Attribute | Type | Semantics |
| :--- | :--- | :--- |
| `feature_set` | `FeatureSet` | The single FeatureSet this model consumes. A model that needs multiple distinct feature vocabularies should be expressed as multiple Model classes wrapped by a Strategy that ensembles them. |
| `resources_train` | `Resources` | Compute allocation for `train()`. See §7. |
| `resources_serve` | `Resources` | Compute allocation for `predict()` at serving time. See §7. May be omitted if equal to `Resources(cpu=2, memory_gb=4)` (the default). |

#### 2.2.4 Required methods

The user subclasses the abstract base class `Model`, which is an `abc.ABC`. The two abstract methods are:

```python
@abstractmethod
def train(self, train: pl.DataFrame, val: pl.DataFrame) -> None:
    """
    Fit the model on `train`, validating on `val`. Mutates `self`.
    Both DataFrames have the schema declared by `feature_set`:
    feature columns, entity columns, plus the target column.
    The target is included; it is the user's responsibility to extract
    it from the DataFrame for fitting.
    Returns None. The fitted state lives on `self`; MLflow logging is
    handled automatically (see §6.1). The user may call mlflow.log_*
    inside train() to record additional metrics; the platform will
    associate them with the active run.
    """

@abstractmethod
def predict(self, features: pl.DataFrame) -> pl.Series:
    """
    Produce predictions for the rows in `features`. The schema of
    `features` matches `feature_set` minus the target column. Returns
    a `pl.Series` of length `features.height`, with index aligned to
    `features` row order. The series's name is conventionally the
    target's column name; the platform does not enforce this but it
    is used in logging.
    For probabilistic models, `predict` returns the point estimate
    (mean or median per the model's choice). Quantile predictions
    are returned by an optional `predict_quantiles` method (see §2.2.6).
    """
```

#### 2.2.5 The contract on `train` and `predict`

Three properties of `train` are platform-relevant:

- **Determinism given inputs.** The same `(train, val)` inputs and the same `__init__` arguments must produce the same fitted state. Random-seeded operations must take their seed from `self` (set in `__init__`) or from a platform-injected seed (see §2.2.7). This is what makes a training run reproducible from MLflow metadata.
- **No external I/O during fit.** `train` must not read external data (HTTP calls, file reads outside MLflow, database queries against non-platform databases). All inputs come through the FeatureSet extraction; all outputs go through MLflow. Violations are not enforced at runtime in v1 but are flagged by static analysis at submission time (see §3.4) and are a CI-blocking lint in the user's repo.
- **Bounded compute.** `train` must complete within the `resources_train` allocation. Out-of-memory, OOM-kill, or timeout (default 24 hours; configurable per-Model via a `train_timeout_hours` class attribute) results in a failed training fold. See §5.

Three properties of `predict` are platform-relevant:

- **Pure given fitted state and inputs.** Same `self` (post-`train`), same `features`, same output. No randomness.
- **Idempotent.** Calling `predict` twice on the same input returns the same output. This is what makes inference replay (PRD §4.1 Beat 6 SHOULD) safe.
- **Schema-stable.** The output `pl.Series` has the same dtype across all calls. The platform records the dtype in the model's MLflow signature.

#### 2.2.6 Optional methods

The Model base class declares the following optional methods. The user overrides them when applicable; the platform detects override via `inspect.getmembers` and adapts behaviour accordingly.

```python
def predict_quantiles(self, features: pl.DataFrame, quantiles: list[float]) -> pl.DataFrame:
    """
    For probabilistic models. Returns a DataFrame with one column per
    requested quantile, named `q_{quantile}` (e.g., `q_0.05`, `q_0.50`,
    `q_0.95`). Rows aligned to `features`.
    Required when the Strategy declares `requires_quantile_predictions = True`,
    or when the BacktestConfig requests quantile-based reporting.
    Default implementation raises NotImplementedError.
    """

def feature_importance(self) -> pl.DataFrame:
    """
    Returns a DataFrame with columns `feature` (str) and `importance`
    (float), sorted by importance descending. Used to populate the
    Models area's importance panel (PRD §4.1 Beat 5).
    Default implementation returns an empty DataFrame.
    """

def serialize(self) -> bytes:
    """
    Returns a bytes payload representing the full fitted state. The
    platform calls this after train() completes and stores the result
    as the model's MLflow pyfunc artefact. The default implementation
    uses cloudpickle on `self`. Override only if you have a more
    compact or audit-friendly format (e.g., LightGBM's native `model_to_string`).
    """

@classmethod
def deserialize(cls, payload: bytes) -> "Model":
    """
    Reverse of serialize. The platform calls this at serving startup
    and at backtest replay. Default implementation uses cloudpickle.
    """
```

The serialization hook exists because cloudpickle, while convenient, is not the right serialisation choice for all model types. LightGBM has a native string format that is smaller, version-stable across LightGBM minor versions, and human-inspectable; a quant who wants that representation in their MLflow artefacts overrides `serialize` and `deserialize` accordingly.

#### 2.2.7 Platform-injected seed

When the platform calls `train`, it sets the seed via the Model's `_platform_seed` attribute (set on `self` before `train` is called). The user is encouraged but not required to read this seed:

```python
def train(self, train: pl.DataFrame, val: pl.DataFrame) -> None:
    seed = getattr(self, "_platform_seed", 42)
    self._lgb = lgb.train(
        params={"seed": seed, "learning_rate": self.learning_rate, ...},
        ...
    )
```

The seed is derived deterministically from the training-run identifier so that re-running a fold from MLflow metadata produces the same fitted state, which is what makes the run reproducible.

#### 2.2.8 Worked example: cross-sectional GBDT

```python
from quantplatform import Model, Resources
import polars as pl
import lightgbm as lgb
import numpy as np

class AlphaModel(Model):
    feature_set = features  # the FeatureSet from §2.1.5
    resources_train = Resources(cpu=8, memory_gb=32)
    resources_serve = Resources(cpu=2, memory_gb=4)

    def __init__(
        self,
        learning_rate: float = 0.05,
        num_leaves: int = 64,
        n_estimators: int = 1000,
    ):
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.n_estimators = n_estimators
        self._lgb: lgb.Booster | None = None
        self._feature_cols: list[str] | None = None

    def train(self, train: pl.DataFrame, val: pl.DataFrame) -> None:
        target_col = self.feature_set.target.column
        entity_cols = self.feature_set.entity_columns
        feature_cols = [c for c in train.columns if c not in entity_cols + [target_col]]

        X_train = train.select(feature_cols).to_numpy()
        y_train = train.get_column(target_col).to_numpy()
        X_val = val.select(feature_cols).to_numpy()
        y_val = val.get_column(target_col).to_numpy()

        self._lgb = lgb.train(
            params={
                "objective": "regression",
                "learning_rate": self.learning_rate,
                "num_leaves": self.num_leaves,
                "seed": getattr(self, "_platform_seed", 42),
            },
            train_set=lgb.Dataset(X_train, label=y_train),
            valid_sets=[lgb.Dataset(X_val, label=y_val)],
            num_boost_round=self.n_estimators,
            callbacks=[lgb.early_stopping(50)],
        )
        self._feature_cols = feature_cols

    def predict(self, features: pl.DataFrame) -> pl.Series:
        X = features.select(self._feature_cols).to_numpy()
        y_hat = self._lgb.predict(X)
        return pl.Series(name="prediction", values=y_hat)

    def feature_importance(self) -> pl.DataFrame:
        gains = self._lgb.feature_importance(importance_type="gain")
        return pl.DataFrame({
            "feature": self._feature_cols,
            "importance": gains,
        }).sort("importance", descending=True)
```

This is the kind of class a quant writes once and never changes during the development of the strategy. The interesting code is in `train` and `predict`; the rest is bookkeeping the SDK requires.

### 2.3 Strategy

#### 2.3.1 Purpose

A `Strategy` turns predictions into target positions. This is the decision boundary: the Model says what the data implies; the Strategy says what to hold given that implication, the eligible universe, the current position, and any additional constraints (turnover budget, sector neutrality, leverage cap).

Separating Model from Strategy is decision 4 above, and it is the most consequential structural choice in the SDK. The justification is twofold: first, in real quant practice the same predictions feed multiple strategies (long-only vs long-short, equal-weight vs vol-targeted, sector-neutral vs not), and a quant who wants to compare four strategies on one model should not have to retrain four models. Second, the validation criteria are different: a Model is judged by IC, R², and PBO; a Strategy is judged by Sharpe, drawdown, capacity, and turnover. Conflating them in one class obscures the criteria.

#### 2.3.2 API

```python
from quantplatform import Strategy, Model
import polars as pl

class LongShortStrategy(Strategy):
    model = AlphaModel  # class reference, not instance

    def positions(
        self,
        predictions: pl.Series,
        universe: pl.DataFrame,
        current: dict[str, float],
    ) -> dict[str, float]:
        ...
```

#### 2.3.3 Required class attributes

| Attribute | Type | Semantics |
| :--- | :--- | :--- |
| `model` | `type[Model]` or `list[type[Model]]` | The Model class(es) whose predictions feed this Strategy. A single class is the common case. A list is for ensembled strategies; the `positions` method receives a list of `pl.Series` in the same order. |

#### 2.3.4 Required method

```python
@abstractmethod
def positions(
    self,
    predictions: pl.Series,
    universe: pl.DataFrame,
    current: dict[str, float],
) -> dict[str, float]:
    """
    Produce target positions given the model's predictions, the
    eligible universe at the decision time, and the current position.

    Arguments:
        predictions: pl.Series of predictions, one per row of `universe`,
                     in the same order. For multi-model strategies this
                     is a list[pl.Series] of the same length as `model`.
        universe:    pl.DataFrame with one row per asset eligible to
                     hold at this decision time. Includes asset_id, any
                     liquidity / market-cap fields the strategy needs,
                     and `prediction` (a copy of `predictions` for
                     convenient join-free indexing).
        current:     dict[asset_id -> current_position] in shares (or
                     contracts, or notional units consistent with the
                     instrument). Assets not currently held are absent
                     from the dict; their current position is implicitly
                     zero.

    Returns:
        dict[asset_id -> target_position] in the same units as `current`.
        Assets the Strategy wants to be flat in are either omitted from
        the dict or set explicitly to 0.0; both are equivalent.
    """
```

#### 2.3.5 Optional class attributes

| Attribute | Type | Default | Semantics |
| :--- | :--- | :--- | :--- |
| `resources_serve` | `Resources` | `Resources(cpu=1, memory_gb=2)` | Compute for `positions()` at serving time. Almost always small; the heavy lifting is in the Model's `predict`. |
| `requires_quantile_predictions` | `bool` | `False` | When True, the platform calls the Model's `predict_quantiles` instead of `predict`, and `predictions` is a `pl.DataFrame` rather than a `pl.Series`. |
| `position_units` | `str` | `"shares"` | One of `"shares"`, `"contracts"`, `"notional_usd"`, `"weight"`. Documents the unit; consumed by the OMS-export contract (§5.10). |

#### 2.3.6 The contract on `positions`

- **Pure function of inputs.** Given the same `(predictions, universe, current)`, the method returns the same dict. No external I/O. No reading of external state (current portfolio NAV from a database, current prices from a vendor API). Inputs that vary across calls must come in through the arguments.
- **Bounded compute.** `positions()` runs inside both the backtest loop and the serving role. The backtest loop calls it many times; the serving role calls it once per cadence. A `positions` method that takes thirty seconds on a thousand-asset universe is a backtest performance problem and a serving latency problem.
- **No side effects on `self`.** The Strategy may have hyperparameters as `__init__` arguments and read them from `self`, but `positions` does not mutate `self`. This is what allows the same Strategy instance to be safely reused across backtest folds and serving calls.

#### 2.3.7 Worked example: long-short with vol-targeted sizing

```python
from quantplatform import Strategy
import polars as pl

class LongShortStrategy(Strategy):
    model = AlphaModel
    position_units = "weight"

    def __init__(
        self,
        long_quantile: float = 0.10,
        short_quantile: float = 0.10,
        target_vol_annualised: float = 0.10,
        max_position_weight: float = 0.02,
    ):
        self.long_quantile = long_quantile
        self.short_quantile = short_quantile
        self.target_vol_annualised = target_vol_annualised
        self.max_position_weight = max_position_weight

    def positions(
        self,
        predictions: pl.Series,
        universe: pl.DataFrame,
        current: dict[str, float],
    ) -> dict[str, float]:
        scored = universe.with_columns(predictions.alias("prediction"))

        long_threshold = scored.get_column("prediction").quantile(1.0 - self.long_quantile)
        short_threshold = scored.get_column("prediction").quantile(self.short_quantile)

        long_assets = scored.filter(pl.col("prediction") >= long_threshold)
        short_assets = scored.filter(pl.col("prediction") <= short_threshold)

        n_long = long_assets.height
        n_short = short_assets.height

        long_weight = min(1.0 / n_long, self.max_position_weight) if n_long > 0 else 0.0
        short_weight = -min(1.0 / n_short, self.max_position_weight) if n_short > 0 else 0.0

        targets: dict[str, float] = {}
        for row in long_assets.iter_rows(named=True):
            targets[row["asset_id"]] = long_weight
        for row in short_assets.iter_rows(named=True):
            targets[row["asset_id"]] = short_weight

        # Vol scaling is applied by the platform's portfolio constructor
        # using the strategy's target_vol_annualised attribute; positions
        # returned here are pre-vol-scaled weights.
        return targets
```

The vol-scaling note in the comment points at a real design choice: the SDK delegates the standard portfolio-construction post-processing (vol targeting, leverage capping, sector neutrality) to the platform's portfolio constructor, configured through the Strategy's class attributes. The user writes the *signal-to-position* logic; the platform applies the *position-to-portfolio* logic. The boundary is documented in the SDK's API reference and is **Open question 4** for v2 (whether to expose the portfolio constructor as a separate user-overridable hook).

### 2.4 WalkForwardConfig

#### 2.4.1 Purpose

`WalkForwardConfig` declares the walk-forward validation regime under which the Strategy will be trained and evaluated. Walk-forward is enforced as a platform property (Key Idea / PRD T3.1-T3.3): a model that has not been walk-forward-validated cannot be promoted to production. The WalkForwardConfig is therefore a required argument to `register()`.

The configuration is versioned with the strategy family. Changing it (a wider window, a shorter step) invalidates prior walk-forward evidence; the platform requires a re-run before the next promotion can pass the gate.

#### 2.4.2 API

```python
from quantplatform import WalkForwardConfig

walk_forward = WalkForwardConfig(
    step="quarter",
    train_window="3y",
    test_window="1q",
    min_folds=8,
    purge_window="5d",
    embargo_window="1d",
    cv_method="cpcv",
    cv_n_groups=10,
    cv_n_test_groups=2,
)
```

#### 2.4.3 Type signature

`WalkForwardConfig` is a Pydantic v2 `BaseModel`:

| Field | Type | Required | Default | Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `step` | `Literal["day", "week", "month", "quarter", "year"]` | yes | — | Step size between consecutive folds. |
| `train_window` | `str` (ISO 8601 duration shorthand) | yes | — | Length of the training window per fold. Accepted formats: `"3y"`, `"36m"`, `"1095d"`, ISO 8601 `"P3Y"`. |
| `test_window` | `str` | yes | — | Length of the out-of-sample (test) window per fold. Same format. |
| `min_folds` | `int` | yes | — | Minimum number of completed folds required to enable promotion. The PRD T3.2 default is 5; the recommended floor for cross-sectional equity is 8 (~ 2 years of quarterly re-evaluation). |
| `purge_window` | `str` | no | `"0d"` | Time gap between the end of the training window and the start of the test window, applied per asset. Defends against label leakage when the target is forward-looking (e.g., a 5-day forward return computed at t requires excluding `[t-5, t]` from the training window for that asset). |
| `embargo_window` | `str` | no | `"0d"` | Additional gap before the next training window starts after a fold's test window ends. Defends against autocorrelation leakage between consecutive folds. |
| `cv_method` | `Literal["cpcv", "kfold", "expanding", "rolling"]` | no | `"cpcv"` | The cross-validation method used *within* the training window for hyperparameter selection. CPCV (Combinatorial Purged Cross-Validation, López de Prado) is the platform default per PRD T3.x and the research synthesis Part 6. |
| `cv_n_groups` | `int` | no | `10` | When `cv_method="cpcv"`, the number of contiguous time groups the training window is divided into. |
| `cv_n_test_groups` | `int` | no | `2` | When `cv_method="cpcv"`, the number of groups held out per CPCV combination; the number of CPCV combinations is `C(n_groups, n_test_groups)`. |
| `mode` | `Literal["expanding", "sliding"]` | no | `"sliding"` | Whether the training window slides forward (`"sliding"`, fixed-length) or expands (`"expanding"`, anchored at the start) with each step. |

#### 2.4.4 Semantics

The platform's walk-forward harness reads the WalkForwardConfig and computes the sequence of folds. For a config of `(step="quarter", train_window="3y", test_window="1q", mode="sliding")` with strategy data starting 2010-01-01 and ending 2025-12-31, the harness produces ~52 folds:

- Fold 1: train on 2013-01-01 → 2015-12-31, test on 2016-01-01 → 2016-03-31.
- Fold 2: train on 2013-04-01 → 2016-03-31, test on 2016-04-01 → 2016-06-30.
- ...and so on, sliding by one quarter per step, until the test window would extend past the data end.

Each fold is dispatched as a separate training job (§5.4). The Model's `train` is called once per fold with the fold's `(train, val)` Polars DataFrames; `val` is a held-out slice within the training window (CPCV-selected when `cv_method="cpcv"`). The Strategy's `positions()` is then called day-by-day across the test window, with the predictions from the fold's trained Model as input.

For single-series models (`entity_columns=["date"]`), the harness uses a contiguous-time split rather than CPCV; the `purge_window` and `embargo_window` are still respected. For cross-sectional models, CPCV is the default, and the `purge_window` is computed per asset based on the target's forward horizon (the platform infers this from the target column name's `_future_{n}d` suffix when present, or from the user's explicit `target_horizon` declaration on the FeatureSet; **Open question 1** — whether to require explicit declaration of target horizon).

#### 2.4.5 Why these defaults

CPCV is the platform default because k-fold cross-validation is broken for financial time series — the temporal ordering matters and naive folds leak information across the boundary. CPCV (López de Prado, *Advances in Financial Machine Learning*, 2018, Ch. 7) is the cleanest published method that preserves temporal ordering while still producing many out-of-sample observations per training window. Reasonable defaults for `cv_n_groups=10` and `cv_n_test_groups=2` produce 45 CPCV combinations per training window — enough variance for PBO computation, not so many that hyperparameter search becomes prohibitive.

The `purge_window` default of zero is deliberately permissive (the platform will not infer it for the user) but the documentation strongly recommends setting it to the target's forward horizon. **Open question 5** is whether the platform should refuse to promote a model whose target has a forward horizon and whose `purge_window` is zero; the recommendation is yes, but the gate is currently warning-only.

### 2.5 BacktestConfig

#### 2.5.1 Purpose

`BacktestConfig` declares the parameters of the backtest engine that runs after walk-forward validation completes. The walk-forward harness produces a sequence of out-of-sample predictions and target positions; the backtest engine simulates those positions through an execution-cost model and produces equity curves, drawdown statistics, factor decompositions, and the headline Sharpe / DSR / PBO metrics surfaced in the Models area.

`BacktestConfig` is decoupled from `WalkForwardConfig` because the same walk-forward output can be backtested under multiple cost assumptions, capacity scenarios, or benchmarks; in v1 the user specifies one BacktestConfig per `register()` call and the platform runs one backtest per walk-forward result. **Open question 6** is whether v2 should support multiple backtests per registration to enable scenario analysis without re-walking-forward.

#### 2.5.2 API

```python
from quantplatform import BacktestConfig

backtest = BacktestConfig(
    cost_model="almgren_chriss",
    cost_params={"permanent_impact_bps": 0.5, "temporary_impact_bps": 1.5},
    capacity_aum_usd=500_000_000,
    benchmark="SPX",
    factor_model="carhart_4",
    rebalance_cadence="daily",
    initial_cash_usd=100_000_000,
    slippage_bps=0.5,
)
```

#### 2.5.3 Type signature

| Field | Type | Required | Default | Semantics |
| :--- | :--- | :--- | :--- | :--- |
| `cost_model` | `Literal["almgren_chriss", "fixed_bps", "linear_impact"]` | no | `"almgren_chriss"` | Transaction-cost model. Almgren-Chriss is the platform default per the research synthesis Part 5. |
| `cost_params` | `dict[str, float]` | no | `{}` | Model-specific parameters. For `almgren_chriss`: `permanent_impact_bps`, `temporary_impact_bps`, `participation_rate_cap`. For `fixed_bps`: `bps_per_trade`. |
| `capacity_aum_usd` | `float` | yes | — | The AUM at which the backtest is sized. Used to compute notional positions and to estimate impact under the cost model. The Models area surfaces capacity sensitivity by re-running the cost model at multiple AUM values; the registered backtest is at the declared AUM. |
| `benchmark` | `str` | no | None | Identifier of the benchmark series (e.g., `"SPX"`, `"CSI300"`, `"AGG"`). Used for relative-return computation in the Reports area (PRD §4.1 Beat 7). |
| `factor_model` | `Literal["fama_french_3", "carhart_4", "hou_mo_xue_zhang_q5", "none"]` | no | `"carhart_4"` | Factor model used for return decomposition. Carhart 4-factor is the v1 default per PRD OQ-9. |
| `rebalance_cadence` | `Literal["daily", "weekly", "monthly", "quarterly"]` | no | `"daily"` | How often the Strategy's `positions()` is invoked during the simulation. |
| `initial_cash_usd` | `float` | no | `100_000_000` | Starting cash in the backtest portfolio. |
| `slippage_bps` | `float` | no | `0.0` | Additional bid-ask slippage applied per trade beyond the cost model's impact. |
| `lookback_buffer` | `str` | no | `"30d"` | Time before the test window's start for which the model has access to data, to allow features that need a rolling history (e.g., 20-day momentum). The platform extracts the FeatureSet from `(test_window_start - lookback_buffer)` to `test_window_end`. |

#### 2.5.4 Semantics

The backtest engine consumes the WalkForwardConfig's fold predictions in temporal order, simulates daily rebalancing under `rebalance_cadence`, applies the cost model to every trade, accrues P&L, and produces a structured `BacktestResult` aggregate containing:

- The equity curve (one row per trading day, with portfolio NAV and benchmark NAV).
- Per-trade fills (asset, date, side, size, executed price, cost).
- Per-asset cumulative position history.
- Sharpe, Sortino, Calmar, DSR, PBO, max drawdown, time in drawdown, recovery time.
- Factor exposures (per the declared `factor_model`) and factor-decomposed returns.
- Capacity-sensitivity table at AUM × {0.5, 1.0, 2.0, 5.0}.

This aggregate is what the Models area's Beat 4 hero screen (PRD §4.1) renders. It is also what the Reports area's quarterly LP report (Beat 7) draws from.

### 2.6 Resources (auxiliary)

`Resources` is the small Pydantic v2 model that declares compute requirements:

```python
from quantplatform import Resources

class Resources(BaseModel):
    cpu: int                                # vCPUs
    memory_gb: int                          # RAM in gigabytes
    gpu: Literal["T4", "L4", "A100", None] = None
    gpu_count: int = 0                      # ignored when gpu is None
    timeout_hours: float = 24.0
```

Use sites: `Model.resources_train`, `Model.resources_serve`, `Strategy.resources_serve`. The platform translates `Resources` into the appropriate cloud allocation per §7.

---

## 3. The `register()` Contract

`register()` is the single wiring step. It is called exactly once per strategy file at module top level. The platform's CLI imports the file, observes the `register()` call, validates the registration, persists it, and dispatches downstream work.

### 3.1 Full signature

```python
from quantplatform import register, WalkForwardConfig, BacktestConfig

def register(
    *,
    strategy: type[Strategy],
    family: str,
    walk_forward: WalkForwardConfig,
    backtest: BacktestConfig,
    hyperparameter_space: dict[str, Any] | None = None,
    serving_schedule: str | None = None,
    description: str = "",
    tags: dict[str, str] | None = None,
    sdk_version: str | None = None,
) -> None:
    ...
```

All arguments are keyword-only (the leading `*` enforces this). Positional invocation is rejected at submission with a structured error.

### 3.2 Argument semantics

| Argument | Type | Required | Semantics |
| :--- | :--- | :--- | :--- |
| `strategy` | `type[Strategy]` | yes | The Strategy subclass to register. The platform reads `strategy.model` to discover the Model class(es) and walks the chain to discover their FeatureSet(s). |
| `family` | `str` | yes | The strategy family identifier. A family groups related registrations (e.g., quarterly hyperparameter retunes of the same strategy archetype). New registrations within the same family share the family's MLflow registered model name; they accumulate as new versions. New families create a new registered model. |
| `walk_forward` | `WalkForwardConfig` | yes | The validation regime. Versioned with the family per §2.4.1. |
| `backtest` | `BacktestConfig` | yes | The backtest regime. Versioned with the family. |
| `hyperparameter_space` | `dict[str, Any] \| None` | no | Hyperparameter search space for Optuna. When None, the platform trains exactly once per fold using the user's `__init__` defaults or the values they instantiated the Model with. When present, the platform runs an Optuna study per fold; see §3.3. |
| `serving_schedule` | `str \| None` | no | A cron-like or named-cadence schedule under which the platform invokes `Strategy.positions()` in production. Examples: `"daily 16:30 ET"`, `"hourly"`, `"0 16 * * mon-fri America/New_York"`. None means the strategy is on-demand only (not scheduled). |
| `description` | `str` | no | Free-text human description; surfaces in the Models area. |
| `tags` | `dict[str, str] \| None` | no | Free-form key-value tags; indexed for search in the Models area. Convention: `{"asset_class": "equity", "horizon": "5d", "geography": "us"}`. |
| `sdk_version` | `str \| None` | no | The SDK version the user expects (e.g., `"1.4.x"`). The platform compares this to the SDK version in the submission environment and refuses submission if the major version differs (see §8). When None, the SDK's currently-installed version is recorded in metadata. |

### 3.3 Hyperparameter space

The `hyperparameter_space` argument is a dict mapping `__init__` parameter name → distribution specifier. The supported distribution specifiers are:

```python
hyperparameter_space = {
    "learning_rate": (0.01, 0.1, "log"),    # Optuna suggest_float, log scale
    "num_leaves":    (16, 256, "int"),      # Optuna suggest_int
    "n_estimators":  (100, 5000, "int"),    # Optuna suggest_int
    "max_depth":     [3, 5, 7, 10, -1],     # Optuna suggest_categorical
    "objective":     ["regression", "regression_l1"],  # categorical
}
```

The mapping is to Optuna's `suggest_*` calls; the tuple form `(low, high, "log"|"linear"|"int")` covers the common numeric-distribution cases, and the list form covers categorical. The platform refuses any parameter name in the dict that is not present in the Model's `__init__` signature; this catches typos at submission time.

The number of trials per fold is platform-configurable per tenant (default 50) and respects a per-fold timeout. The selection criterion is the validation-set IC for cross-sectional models, RMSE for regression, and the user can override via a `hyperparameter_metric` argument (**Open question 7** — whether to expose this in v1).

### 3.4 What `register()` does at submission time

The CLI's `quant submit my_strategy.py` (§4.1) invokes the following sequence:

1. **Import the strategy file.** The platform creates a sandboxed Python interpreter with the SDK installed, imports the file, and captures the `register()` call. A file with zero `register()` calls fails submission. A file with more than one `register()` call is allowed; each becomes an independent registration in the same submission transaction.
2. **Reflect on the Strategy class.** Read `strategy.model`, walk to the Model class(es), read their `feature_set`, walk to the FeatureSet(s).
3. **Validate the FeatureSet(s).** For each FeatureSet, issue a `LIMIT 1` Polars query against the gold layer with the declared sources, columns, and entity columns. Failures: missing source, missing column, type mismatch, wildcard expansion to zero columns.
4. **Validate the Model class(es).** Verify `train` and `predict` are overridden (not the abstract base class's `NotImplementedError`); verify class attributes are declared; verify `Resources` instances are well-formed.
5. **Validate the Strategy class.** Verify `positions` is overridden; verify `model` references a valid Model class; verify class attributes are declared.
6. **Validate the configurations.** Pydantic validation on WalkForwardConfig, BacktestConfig, Resources. Cross-field validation: `walk_forward.train_window` must exceed `walk_forward.test_window` by a configurable factor (default 4x); `backtest.lookback_buffer` plus `walk_forward.train_window` must fit within available data history.
7. **Static analysis on `train` and `predict`.** Lint pass: detect external I/O calls (`requests.*`, `urllib.*`, `socket.*`, file open outside `mlflow.*`), warn on randomness without `_platform_seed` use, warn on use of pandas instead of polars (info-level, not blocking).
8. **Persist the registration.** Insert a row in the `strategy_registrations` table with the family, the strategy class qualified name, the configurations (serialised to JSON via Pydantic), the file's content hash, the resolved git commit SHA (when the submission is from a git working directory), the SDK version, and the user identity from the platform's session.
9. **Emit the `StrategyRegistered` event.** This is the CQRS event (Chapter 7) that triggers downstream worker activity: the training-fold dispatcher, the walk-forward orchestrator, the audit-log entry.

### 3.5 What `register()` does at runtime (none)

`register()` returns `None` immediately at runtime. It does not block on platform calls, does not make HTTP requests, does not write to local files. The submission CLI is the only thing that observes the call; in any other context (a notebook the user runs to test the strategy file imports cleanly, a CI lint that imports the module to verify syntax), `register()` is a no-op that records its arguments to a thread-local for inspection.

This is critical: the user's strategy file must be importable in environments that do not have platform credentials (a fresh laptop, a CI runner with no secrets). The decoupling between `register()` and platform-side actions is what makes that possible.

### 3.6 Dagster asset definition emission

Beyond persisting the registration row, `register()` also translates the StrategySpec into a Dagster asset definition file written to a watched directory inside the tenant's deployment. Dagster (added to v1 per the blueprint's revised stance on Ch. 15) is the platform's asset-orchestration layer; it coexists with PGMQ (the CQRS message bus) and APScheduler (the cron-cadence scheduler) and adds no new infrastructure — it runs as another role on the existing Cloud Run footprint and persists its own state in the existing Postgres instance.

The translation is mechanical and the asset names are deterministic from the strategy spec. For a registration with `family="us_equity_long_short_alpha158"`, the emitted asset definition declares the following software-defined assets (Dagster's `@asset` model, not its job/op model):

- `bronze_us_equity_long_short_alpha158_data`
- `silver_us_equity_long_short_alpha158_features`
- `gold_us_equity_long_short_alpha158_features`
- `training_run_us_equity_long_short_alpha158_<run_id>`
- `model_version_us_equity_long_short_alpha158_<version>`
- `inference_targets_us_equity_long_short_alpha158_<date>`

The first three reuse the existing medallion projection (Chapter 8); the latter three are dynamic assets keyed by the run / version / inference date. The user does not write Dagster code; the SDK does. The asset graph is the platform's view-of-state and is exposed read-only through the BFF (the quant sees lineage; the quant does not author it). Whether quants should be allowed to write `@asset` directly is **Open question 11** (§12).

---

## 4. The CLI

The platform ships a single CLI binary, `quant`. It is the operator's interface; the React UI is built on the same APIs the CLI calls. Commands are designed to be scriptable (machine-readable JSON output via `--json` flag) and human-friendly (rich terminal output by default).

### 4.1 `quant submit`

**Signature:** `quant submit <file_or_directory> [--family <override>] [--dry-run] [--json]`

**Behaviour:** Performs steps 1-9 of §3.4 against the platform. On success, prints the registration ID and a URL pointing at the Models area for the resulting strategy family. On failure, prints a structured error pointing at the offending field (e.g., `FeatureSet 'us_equity_alpha158_v1': source 'fundamentals' references gold table 'gold.us_equity_fundamentals' which does not exist in tenant 'morgan-fund'`).

The `--family` flag overrides the `family` argument in the file's `register()` call (useful for parameter sweeps that share a strategy file but differ by family identifier).

The `--dry-run` flag performs steps 1-7 (validation only) and skips persistence, event emission, and downstream dispatch. The `--json` flag emits all output as JSON for programmatic consumption.

### 4.2 `quant run`

**Signature:** `quant run <registration_id> [--folds <n>] [--from-fold <n>] [--no-backtest] [--json]`

**Behaviour:** Manually triggers a walk-forward run for an existing registration. Useful for re-running a registration whose previous run failed midway, for re-running with a refreshed dataset, or for running a subset of folds during debugging.

`--folds <n>` limits the run to the first N folds. `--from-fold <n>` resumes from fold N (skipping folds 1..N-1, presumably because they completed earlier). `--no-backtest` skips the backtest stage; the walk-forward predictions are produced and stored but the backtest engine is not invoked.

### 4.3 `quant promote`

**Signature:** `quant promote <model_version_id> [--reason <text>] [--alias <name>] [--json]`

**Behaviour:** Promotes a specific MLflow model version to the production alias (default) or to a named alias. Equivalent to clicking the "Promote" button in the Models area's Beat 5 UI (PRD §3.3). Required by the gate enforcement (§5.7): the promotion blocks if PBO > threshold, walk-forward folds < `min_folds`, or DSR < threshold.

`--reason` is the required justification text per PRD US-1.2. The CLI refuses to invoke the API without it. `--alias` defaults to `production`; alternative aliases are `staging`, `champion`, `challenger`, etc.

### 4.4 `quant inspect`

**Signature:** `quant inspect <object_id> [--json]`

**Behaviour:** Polymorphic introspection. The argument is a registration ID, a model version ID, a training-run ID, an inference ID, or a backtest result ID. The CLI dispatches to the appropriate platform endpoint and prints a structured summary: for a registration, the family / strategy / model / feature set / configurations; for a training run, the fold metadata, MLflow run URL, metrics, status; for an inference, the request / output / model version / latency / lineage chain.

This is the CLI complement to the Models / Deployments area UIs and is the path an operator uses to debug from a terminal during a demo.

### 4.5 `quant local`

**Signature:** `quant local <subcommand>` where subcommands include `train`, `walk-forward`, `backtest`, `serve`, `replay`.

**Behaviour:** Runs the platform's training, walk-forward, backtest, or serving logic against a *local* copy of the gold layer (the docker-compose stack per Chapter 11). The strategy file is the same; the `Resources` declarations are honoured up to the local machine's capacity (with warnings if the user requested more than is available). MLflow tracking points at the local MLflow server.

This is the inner-loop developer experience. A quant iterating on a feature function or a hyperparameter setting runs `quant local train my_strategy.py --fold 1` and gets a result in minutes rather than waiting for cloud dispatch. The docker-compose stack is the same one CI uses (Chapter 11), so passing locally means the strategy will not fail at submission for a class of submission-time errors.

`quant local replay <inference_id>` reproduces a single historical inference end-to-end on the local stack, given the inference ID from the production audit log. This is the "Priya's 60-second answer" capability (PRD US-2.1) exercised from the operator's terminal.

### 4.6 Other commands

For completeness, the CLI surface also includes:

- `quant ls families` — list all strategy families in the tenant.
- `quant ls runs <registration_id>` — list training runs for a registration.
- `quant logs <run_id>` — stream training-run logs.
- `quant audit verify` — runs the audit-chain verification (PRD T5.4) and reports the current head hash.
- `quant init` — scaffolds a new strategy file from a template.

These are not load-bearing in the demo narrative but matter for daily operator and developer use.

---

## 5. End-to-End Lifecycle

This section walks through what happens between `quant submit my_strategy.py` and a target-position file landing in the customer's GCS bucket the next trading day. Each beat names the platform component (worker role, table, event, API call) so an implementer can trace the flow against the rest of the blueprint.

### 5.1 Beat 0 — submission

The user runs `quant submit my_strategy.py` from their development environment. The CLI authenticates via the platform's session (an OIDC-issued JWT, Chapter 6), POSTs the file's contents to `/commands/submit-strategy`, and waits for the response.

The `api` role (Chapter 7 §REST API structure) receives the POST. The handler instantiates a sandboxed sub-interpreter, imports the file, captures the `register()` call(s), and runs the §3.4 validation steps. On validation failure, the handler returns a 400 with the structured error and no state change occurs.

On validation success, the handler enters a single Postgres transaction and:

1. Inserts a row into `strategy_registrations`.
2. Appends a `StrategyRegistered` event to the `events` table.
3. Enqueues a `walk_forward_dispatch` message on PGMQ.
4. Inserts a row into `audit_log` recording the submission with the chained hash (PRD T5.1).

The transaction commits atomically. The handler returns 200 with the registration ID.

### 5.2 Beat 1 — walk-forward dispatch

A `worker-walk-forward` (a new role, added per PRD T1.x; see §6.4 for placement) consumes the `walk_forward_dispatch` message. It reads the registration, computes the fold sequence per `WalkForwardConfig`, and enqueues one `training_fold` message per fold on the `training` PGMQ queue.

For a `(step=quarter, train_window=3y, test_window=1q)` config over 16 years of data, this produces ~52 fold messages. Each carries the registration ID, the fold index, the train window bounds, the test window bounds, and the FeatureSet identifier (so the gold-extraction layer knows which tables to read).

### 5.2a Beat 1a — Dagster materialization

In parallel with the PGMQ fan-out, the registration's Dagster asset definition (emitted at submission per §3.6) is now live in the tenant's Dagster instance. The fold-by-fold training run is a *dynamic* Dagster asset graph: the parent `training_run_<family>_<run_id>` asset declares one downstream partition per fold, and each fold materialization is a separate Dagster run. The `worker-walk-forward` issues a Dagster `materialize` call carrying the same fold parameters it puts on PGMQ; PGMQ remains the work-handoff substrate that the worker fleet consumes, while Dagster owns the *view-of-state* that the BFF surfaces in the lineage UI.

The two are not redundant. PGMQ provides the at-least-once delivery semantics and back-pressure that the worker fleet relies on; Dagster provides the asset graph, the materialization status, the lineage edges, and the visual surface. A fold's Dagster run reaches `MATERIALIZED` when its corresponding `TrainingFoldCompleted` event is observed (Beat 4); on failure, Dagster's run record marks the asset partition as failed and the failure surfaces in the read-only Dagster UI exposed through the BFF.

### 5.3 Beat 2 — gold-layer extraction per fold

A `worker-training` (Chapter 7 §Single image, multiple roles) consumes a `training_fold` message. It reads the FeatureSet from the registration, issues the Polars query against the gold layer with the fold's bounds and the `_knowable_at <= train_window_end` filter, and materialises a `pl.DataFrame` for the training data and a separate one for the in-window validation slice (CPCV-selected per `WalkForwardConfig.cv_method`).

The extraction is materialised to a temporary Parquet file in GCS keyed by `(registration_id, fold_index)`. The hash of this file is the *dataset fingerprint* logged with the MLflow run; it is the basis for the reproducibility guarantee (Chapter 9 §Data extraction and reproducibility).

### 5.4 Beat 3 — training job dispatch

The `worker-training` reads the Model's `resources_train` declaration. If the Resources fit within Cloud Run Jobs constraints (≤ 32 vCPU, ≤ 128 GB memory, no GPU), the worker submits a Cloud Run Job carrying the platform's container image with `ROLE=training-fold` and the fold parameters as environment variables. If GPU is required or resources exceed the Cloud Run cap, the worker submits a Vertex AI Custom Training job with the equivalent parameters; the choice is made by §7.2's mapping table.

Either dispatch is asynchronous. The worker records the cloud job identifier in the `training_runs` table and emits a `TrainingFoldStarted` event.

### 5.5 Beat 4 — model fit inside the job

The Cloud Run Job (or Vertex AI Custom Training job) starts the platform's image with the `training-fold` role. The role's startup logic:

1. Downloads the dataset Parquet from GCS, loads it as a `pl.DataFrame`.
2. Imports the user's strategy file from the registration's content hash (the file is stored in GCS as part of submission).
3. Instantiates the Model class. If `hyperparameter_space` is declared, the role runs an Optuna study with the configured trial count; each trial instantiates the Model with sampled parameters, calls `train(train, val)`, and reports the validation metric. The best trial's fitted Model is the fold's output. If no `hyperparameter_space`, the Model is instantiated once with the user's defaults.
4. Calls `Model.train(train, val)`. The role injects `_platform_seed` derived from the run identifier.
5. On completion, calls `Model.serialize()` to obtain the artefact bytes and writes them to MLflow as the run's `pyfunc` artefact (Chapter 9 §Model packaging).
6. Logs metrics (training loss curve, validation IC / RMSE / R², feature importance via `feature_importance()` if implemented), parameters (the Model's `__init__` arguments), and the dataset fingerprint hash to the MLflow run.
7. Emits a `TrainingFoldCompleted` event with the MLflow run ID.

### 5.6 Beat 5 — walk-forward evaluation

When all fold's `TrainingFoldCompleted` events have arrived (the `worker-walk-forward` listens on the projection that aggregates them), the worker proceeds to the OOS evaluation stage. For each fold, the worker:

1. Loads the fold's Model from MLflow via `Model.deserialize(payload)`.
2. Extracts the fold's test-window data from the gold layer, materialises it as `pl.DataFrame`.
3. Iterates over the test window in `BacktestConfig.rebalance_cadence` steps. At each step:
   - Filters the test data to rows knowable at this step (`_knowable_at <= step_date`).
   - Calls `Model.predict(features)` to obtain predictions.
   - Calls `Strategy.positions(predictions, universe, current)` to obtain target positions.
   - Records the (step_date, predictions, positions) tuple.
4. Persists the fold's predictions and positions to the `walk_forward_results` table.

When all folds have completed evaluation, the worker emits a `WalkForwardCompleted` event.

### 5.7 Beat 6 — PBO and DSR computation

A `worker-backtest` consumes the `WalkForwardCompleted` event. It runs the Polars-based backtest engine (Chapter 7's reference architecture; per PRD T1.4) over the consolidated walk-forward output:

1. Concatenates the per-fold (step_date, predictions, positions) sequences into a continuous time series.
2. Simulates execution under `BacktestConfig.cost_model` and `cost_params`, producing per-trade fills, per-asset cumulative positions, and the equity curve.
3. Computes the headline metrics: Sharpe, Sortino, Calmar, max drawdown, time in drawdown, recovery time.
4. Computes PBO using the combinatorially-symmetric cross-validation variant (López de Prado, *AFML*, Ch. 11). The PBO computation requires the per-fold OOS Sharpes plus the per-fold IS Sharpes; both are produced by the walk-forward stage.
5. Computes DSR (Bailey & López de Prado, 2014) from the headline Sharpe, the number of trials (the registration's hyperparameter trial count summed across folds), and the OOS Sharpe variance.
6. Computes factor exposures and decomposed returns per `BacktestConfig.factor_model`.
7. Computes the capacity-sensitivity table.
8. Persists the full `BacktestResult` aggregate.
9. Emits a `BacktestCompleted` event.

### 5.8 Beat 7 — registry entry and gate evaluation

A `worker-registry` (small, possibly co-resident with `worker-backtest`) consumes the `BacktestCompleted` event. It:

1. Promotes the best-performing fold's MLflow run to a *registered model version* under the family's name. (For a multi-fold ensemble strategy, the platform may register the ensemble; this is **Open question 8** and v1 defaults to single-best-fold.)
2. Attaches the structured metadata: dataset fingerprint, walk-forward configuration, backtest result (with PBO, DSR), registration ID, code commit SHA.
3. Evaluates the promotion gate: `PBO < tenant_pbo_threshold` (default 0.7), `DSR > tenant_dsr_threshold` (default 1.0), `walk_forward_completed_folds >= walk_forward.min_folds`. If all pass, the version is *eligible for promotion* (the `production` alias may be moved to it via §5.9). If any fail, the version is *blocked*; the Models area surfaces the failure with the specific failed gate.
4. Emits a `ModelVersionRegistered` event.

### 5.9 Beat 8 — manual promotion (the human-in-the-loop step)

The user (or the platform's automated promotion policy, if configured) reviews the registered version in the Models area's Beat 5 hero screen (PRD §3.3). They click "Promote", supply the required reason text per PRD US-1.2, and confirm.

The `api` role handles the promote command:

1. Re-evaluates the gate (defence in depth; the gate may have changed if thresholds were updated).
2. Calls MLflow to move the `production` alias to the new version.
3. Appends a `ModelPromoted` event to the event log.
4. Inserts an `audit_log` row with the chained hash, the user identity, the reason, and the (old version, new version) transition.
5. Enqueues a `model_serving_reload` message to the `serving` PGMQ queue.

All in one Postgres transaction (Chapter 5 §Postgres-centric).

### 5.10 Beat 9 — serving lazy-reload

The `worker-inference-batch` (or, for synchronous serving, the `api` role's serving subsystem; Chapter 9 §Serving architecture) listens on `model_serving_reload`. On receipt:

1. Downloads the new model version's `pyfunc` artefact from MLflow to the local cache.
2. Holds the old version in memory until in-flight requests drain (the lazy-reload pattern in Chapter 9).
3. Starts routing new requests to the new version.
4. Logs the swap in the `inference_log` table.

### 5.11 Beat 10 — scheduled inference

The `scheduler` role (Chapter 7 §Single image, multiple roles; APScheduler) reads the registration's `serving_schedule` (e.g., `"daily 16:30 ET"`) and emits a `scheduled_inference` message on the appropriate cadence. The `worker-inference-batch` consumes the message:

1. Materialises the FeatureSet at the inference `as_of` (typically the message's emission time minus the data-availability lag).
2. Calls `Model.predict(features)` on the production version.
3. Calls `Strategy.positions(predictions, universe, current)` where `current` comes from the platform's portfolio-state projection (which tracks what positions were last announced; in v1 this is the last announced target, since there is no broker integration to confirm fills).
4. Writes the target positions to a structured Parquet file at `gs://{tenant-bucket}/serving/{registration_id}/{date}/positions.parquet`.
5. Emits a `TargetPositionsPublished` event with the file URI and content hash.
6. Records the inference in `inference_log` with the same fields described in Chapter 9 §Inference auditability.

The customer's OMS polls the bucket (or subscribes to GCS object notifications) and consumes the file. The platform does not invoke the OMS; the boundary is a file-and-event interface per decision 8.

### 5.12 Beat 11 — audit trail

Every step above emits an `audit_log` row with the cryptographic chain hash. The audit log captures: who initiated (user identity from session, or `system` for scheduled runs), what action (`StrategyRegistered`, `TrainingFoldStarted`, `BacktestCompleted`, `ModelPromoted`, `TargetPositionsPublished`), what objects were touched (registration ID, model version ID, file URIs), and an optional reason string for human-initiated actions. The chain is verifiable by `quant audit verify` (§4.6).

This is the evidence trail that PRD US-2.1 (specific inference drill-down for ODD) exercises: Priya asks "show me the inference from 18 months ago," the operator runs `quant inspect <inference_id>`, the platform walks the lineage from inference → model version → walk-forward result → training fold → dataset fingerprint → bronze source files. The lineage is queryable because every event is immutable and every event references its predecessors.

---

## 6. Relationships to Other Platform Components

The SDK does not reinvent the rest of the platform. It is the user-facing surface that delegates everything else to the components described in the blueprint. This section names each integration point.

### 6.1 MLflow

The SDK uses MLflow (Chapter 9) for experiment tracking, model registry, and artefact storage. The integration shape:

- Each `register()` call corresponds to one MLflow registered model (named `{family}`). New `register()` calls within the same family create new versions on the existing registered model.
- Each training fold corresponds to one MLflow run. The run's parameters are the Model's `__init__` arguments; the metrics include the validation IC/RMSE/R², the feature importance (if implemented), the dataset fingerprint hash; the artefacts include the `pyfunc` package and any user-logged artefacts (via `mlflow.log_*` inside `train`).
- The `pyfunc` artefact is constructed automatically by the platform from `Model.serialize()` plus a small wrapper that calls `Model.deserialize()` on load and exposes a `predict(model_input)` method that calls `Model.predict(model_input)`. The serving path's `pyfunc` invocation is therefore the same path the SDK uses internally.
- Promotion uses MLflow Model Aliases (Chapter 9 §Experiments, runs, and models; the platform follows the Aliases pattern, not the deprecated Stages). The `production` alias is moved by the §5.9 promote command.
- The MLflow tracking server is a per-tenant Cloud Run service (Chapter 9), reachable from the SDK at the URL the platform injects into the training job's environment.

The user does not call MLflow directly in their strategy file. The platform mediates. A user may *optionally* call `mlflow.log_metric` or `mlflow.log_artifact` inside `train()` to record additional information; the platform sets up an active MLflow run before invoking `train`, so these calls land in the right place.

### 6.2 Polars

Polars is the lingua franca per decision 3. The SDK signatures are typed in `pl.DataFrame` and `pl.Series`. The gold-extraction layer produces `pl.LazyFrame`s; the platform calls `.collect()` before passing to user code. The user is free to use Polars-native operations inside `train` and `predict`; conversion to NumPy or Arrow at the model-fitting boundary is the user's responsibility (and is the common pattern, since most ML libraries take NumPy arrays).

The SDK does not wrap Polars in a thin abstraction. A user who wants `pl.col("foo").rolling_mean(20)` writes exactly that. The platform's value-add is the upstream extraction and the downstream serialisation; the user's modelling code is unconstrained Polars-and-PyData.

### 6.3 Medallion gold layer

The FeatureSet's `sources` dict references gold-layer tables (Chapter 8 §Gold). The platform's gold layer is conventional: typed Postgres tables (or TimescaleDB hypertables for time-series-heavy gold tables) with bi-temporal columns (`_knowable_at`, `_valid_from`, `_valid_to`) per Chapter 8 §Point-in-time correctness.

The SDK does not provide a way to write to gold. Gold is produced by the silver-to-gold pipeline workers (Chapter 7's `worker-pipeline-silver`); the SDK only reads. A user who needs a feature that does not exist in gold contacts their data engineering function (or, in a small fund, writes the silver-to-gold transformation themselves and submits it through the data pipeline path, which is *not* the SDK). The SDK will validate at submission time that the requested gold tables and columns exist; missing gold is an error message, not a silent failure.

### 6.4 PGMQ

PGMQ (Chapter 5 §Postgres-as-platform; Chapter 7 §CQRS) is the platform's queueing substrate. The SDK does not interact with PGMQ directly. The CLI's `quant submit` calls a REST endpoint that, inside its handler, enqueues PGMQ messages; the user does not see or configure queues. The lifecycle described in §5 is implemented in terms of PGMQ message handoffs between worker roles.

The SDK's relationship to PGMQ is: every `register()` call ultimately produces a chain of PGMQ messages that flow through the worker fleet. The user's mental model of submission is "fire and forget; check progress in the UI"; the implementation is the message chain.

### 6.5 Cloud Run Jobs

For training folds whose `Resources` declarations fit Cloud Run Jobs constraints (the common case for GBDT and small-to-medium scikit-learn models), the platform dispatches to Cloud Run Jobs (Chapter 10 §Compute targets). The mapping from `Resources(cpu=N, memory_gb=M, gpu=None)` to a Cloud Run Job's `--cpu N --memory Mgi` is direct. The job's container is the platform image with `ROLE=training-fold`; the job's args carry the registration ID and fold parameters.

Cloud Run Jobs' max execution time is 168 hours (per GCP docs as of 2026-04). The SDK's `Resources.timeout_hours` defaults to 24; the user can raise it up to the cap. Beyond the cap, the user must use Vertex AI Custom Training (which has no such hard cap).

### 6.6 Vertex AI Custom Training

For training folds requiring GPU or exceeding Cloud Run Jobs constraints, the platform dispatches to Vertex AI Custom Training (Chapter 9 §Training environment, category 2). The mapping table is in §7.2.

The same platform image is used; the entry point is the same `ROLE=training-fold`; the only difference is the cloud job submission API. The user's strategy file is unchanged regardless of where the training fold runs — this is what makes "the same code in research and production" extend to "the same code regardless of compute target."

### 6.7 Dagster

Dagster is the platform's asset-orchestration layer (added to v1 per the blueprint's revised Ch. 15 stance) and one of the SDK's integration points. The shape:

- The SDK's `register()` call writes a Dagster asset definition file per §3.6. The asset names are deterministic from the strategy spec; the user does not author Dagster code.
- The asset graph is software-defined (Dagster `@asset`), not job/op-defined. Each fold's training is a partition of the parent training-run asset; each model version is its own asset; each scheduled inference materialises an `inference_targets_<family>_<date>` asset.
- Dagster runs on the existing Cloud Run footprint as another role stamped from the platform image, persists its state in the existing Postgres instance, and adds no new infrastructure.
- Dagster coexists with PGMQ and APScheduler. PGMQ remains the worker-handoff queue; APScheduler remains the cron-cadence scheduler that triggers `serving_schedule` cycles. Dagster owns the view-of-state — the asset graph, the materialization status, the lineage edges — and is the source of truth for the lineage UI exposed through the BFF.
- The Dagster UI is exposed *read-only* through the platform's BFF. Quants and operators see the lineage from bronze data through gold features through training runs through model versions through inference targets; they do not author Dagster jobs or alter schedules through the Dagster UI. Mutations go through the SDK and the platform's CLI per §4.

The user's strategy file is unchanged by Dagster's presence. The SDK's API surface (FeatureSet, Model, Strategy, register) is the same; the platform's `register()` translates that API into Dagster assets transparently.

### 6.8 Worker roles (recap)

The new and modified worker roles introduced or extended by the SDK lifecycle, summarised against Chapter 7 §Single image, multiple roles:

| Role | Responsibility | New / existing |
| :--- | :--- | :--- |
| `api` | Hosts the SDK CLI's REST endpoints (`/commands/submit-strategy`, etc.) | Existing |
| `worker-walk-forward` | Computes fold sequence; dispatches training-fold messages; consolidates fold results | New (PRD T1.1 family) |
| `worker-training` | Extracts dataset; submits Cloud Run Job or Vertex AI Custom Training | Existing (modified) |
| Cloud Run Job / Vertex AI training | Runs `Model.train`; logs to MLflow | Cloud-side compute |
| `worker-backtest` | Computes PBO/DSR; runs backtest engine; persists BacktestResult | New (PRD T1.1) |
| `worker-registry` | Creates MLflow registry entries; evaluates promotion gates | New (small) |
| `worker-inference-batch` | Scheduled inference; target-position publication | Existing (modified) |
| `scheduler` | Emits `scheduled_inference` messages per `serving_schedule` | Existing |

Each role is a separate Cloud Run service stamped from the same image, autoscaled by its respective queue's depth (Chapter 7 §Worker anatomy).

---

## 7. Resources Model

`Resources` is the bridge between the user's modelling concerns and the platform's compute allocation. This section describes how `Resources` is interpreted in practice.

### 7.1 The model

`Resources(cpu, memory_gb, gpu, gpu_count, timeout_hours)` is the full surface. Defaults: `gpu=None`, `gpu_count=0`, `timeout_hours=24.0`.

Constraints validated at submission:

- `cpu` must be a positive integer.
- `memory_gb` must be a positive integer.
- `gpu` must be one of `None`, `"T4"`, `"L4"`, `"A100"` (the GPU types currently supported on the platform's GCP zones; extensible).
- `gpu_count` must be `0` if `gpu is None`, else `>= 1`.
- `timeout_hours` must be in `(0, 168.0]`.

### 7.2 Mapping to cloud allocations

The platform's training dispatcher consults the following mapping at training-fold dispatch time:

| Resources | Cloud target | Allocation shape |
| :--- | :--- | :--- |
| `cpu ≤ 8, memory_gb ≤ 32, gpu=None` | Cloud Run Jobs | `--cpu N --memory {memory_gb}Gi` |
| `cpu ≤ 32, memory_gb ≤ 128, gpu=None` | Cloud Run Jobs | `--cpu N --memory {memory_gb}Gi` (Cloud Run's high-resource tier) |
| `gpu="T4" or "L4", gpu_count=1, memory_gb ≤ 64` | Vertex AI Custom Training | `n1-standard-{cpu*4}` + `NVIDIA_TESLA_T4` (or L4) |
| `gpu="A100", gpu_count ∈ {1,2,4,8}` | Vertex AI Custom Training | `a2-highgpu-{gpu_count}g` |
| `cpu > 32 or memory_gb > 128` (no GPU) | Vertex AI Custom Training | `n2-highmem-{...}` |

The mapping is configuration in the platform's deployment, not user-visible. The user declares their resource needs; the platform picks the target. **Open question 3** is whether the user should be able to *force* a specific target (some quants have strong preferences); v1 does not expose this.

### 7.3 Serving allocations

`resources_serve` is interpreted differently:

- For models served *in-process* by the `worker-inference-batch` (the v1 default), the role's container is sized to the maximum of `resources_serve` across all currently-serving Models. A new model whose `resources_serve` exceeds the role's current sizing triggers a Cloud Run revision deployment with a larger container shape.
- For models requiring GPU at serving (rare; usually a Transformer for cross-asset attention; Chapter 9 §High-throughput or GPU-bound serving), the platform deploys a *dedicated Cloud Run service per model*, again stamped from the same image. The user does not configure this; the platform does it automatically when `resources_serve.gpu is not None`.

### 7.4 Dependencies

The SDK does not declare Python package dependencies. The platform's container image is the dependency manifest: any package the user imports in their strategy file must be in the image. The image's manifest is published to the user's tenant (a `quant inspect environment` command, planned for v1.1) and is updated by the platform on a release cadence.

This is a deliberate choice: per-strategy dependency management is one of the most reliable sources of "works in research, fails in production" failures. By declaring the dependency set centrally and shipping the same image to research and production (Chapter 11 §Local development), the platform eliminates this class of failure. A user who needs a package not in the image opens a request with the platform team; the package is added in the next release.

This is the same reasoning Chapter 11 applies to the local docker-compose stack: one image, many roles, common dependency closure. The SDK is a node in that graph, not an exception to it.

**Open question 9** is whether v1 should support per-strategy `pip install` overlays for experimental packages. The architectural argument against is the integrity of the parity guarantee; the practical argument for is that quants will hit a missing-package wall periodically and the platform team's response time is finite. The current spec defers this to v2.

---

## 8. Versioning Policy

The SDK is a public API. It is what the user imports in their strategy file. Breaking changes to the SDK break the user's strategy file. The versioning policy below makes the rules explicit so that both sides — platform team and customer quants — know what to expect.

### 8.1 Semver

The SDK is versioned per [Semantic Versioning 2.0](https://semver.org/spec/v2.0.0.html). The version components mean exactly what semver says they mean:

- **MAJOR** version increments mean a breaking API change. A user's strategy file written against MAJOR=N may not work against MAJOR=N+1 without modification.
- **MINOR** version increments are additive. New abstractions, new optional fields on existing Pydantic models, new methods on `Model` and `Strategy` (with default implementations on the ABC), new CLI commands. A user's strategy file from MINOR=4 works unchanged on MINOR=5.
- **PATCH** version increments are bug fixes and internal improvements. No API change.

The platform makes a binding commitment: **within a major version, no breaking change**. A strategy file submitted against SDK 1.0.0 will continue to work against any 1.x.y release.

### 8.2 What counts as a breaking change

To make the boundary unambiguous:

- Changing the type of an existing Pydantic field is breaking.
- Removing an existing Pydantic field is breaking.
- Changing the signature of an existing method on `Model` or `Strategy` (including renaming arguments) is breaking.
- Adding a new required field to an existing Pydantic model is breaking.
- Removing or renaming a CLI command is breaking.
- Changing the semantics of an existing method (same signature, different behaviour) without a version-gated opt-in is breaking.

The following are *not* breaking:

- Adding a new optional Pydantic field with a default.
- Adding a new method to `Model` or `Strategy` with a default implementation.
- Adding a new CLI command.
- Adding a new value to a `Literal` type whose existing values continue to work.
- Tightening validation in a way that previously-invalid inputs now fail more clearly (provided previously-valid inputs continue to work).

### 8.3 Pinning the SDK version in a strategy file

The user pins via the `sdk_version` argument to `register()`:

```python
register(
    strategy=LongShortStrategy,
    family="us_equity_long_short_alpha158",
    walk_forward=walk_forward,
    backtest=backtest,
    sdk_version="1.4",
)
```

The platform's submission CLI compares the declared version to the SDK installed in the submission environment:

- Same MAJOR, declared MINOR ≤ installed MINOR: accept (the installed SDK is forward-compatible).
- Same MAJOR, declared MINOR > installed MINOR: warn (the user expects a newer SDK than is installed; the file may use unsupported features).
- Different MAJOR: reject (the user's file is from a different generation of the SDK and cannot be safely interpreted).

The user is encouraged but not required to pin. A file with no `sdk_version` is recorded as having been submitted against the SDK version in the submission environment, which becomes its de-facto pin.

### 8.4 Deprecation

When the platform team intends to remove or change a feature in the next major release, the feature is *deprecated* in a minor release of the current major. Deprecated features:

- Continue to work with no behaviour change.
- Emit a `DeprecationWarning` at submission time, surfacing in the CLI output and in the audit log.
- Are documented in the SDK's `DEPRECATIONS.md` with the planned removal version, the recommended migration, and the rationale.

The minimum deprecation window is **two minor releases** (typically ~6 months at the platform's expected cadence). The platform commits to no deprecation-then-removal cycle shorter than that.

### 8.5 Major version cadence

The current expectation is one major release every 18-24 months. SDK 1.x is the v1 release; 2.x will accumulate the deferred items from §12 plus whatever the platform team learns from the first three pilots. There is no plan for SDK 2.x within the v1 build window.

A migration guide accompanies every major release. The Qlib migration (§11) is the template: a separate document showing the canonical examples in the new and old idioms side-by-side.

### 8.6 The platform side of the contract

The platform's API surface (the REST endpoints the SDK calls; the Postgres schemas the platform writes; the MLflow conventions) is *not* the SDK's API. The platform may evolve the REST endpoints as it pleases, provided the SDK continues to expose the same surface to the user. The SDK is the only stable public contract; everything beneath it is internal.

This is an intentional decoupling. It lets the platform team refactor freely below the SDK boundary without breaking customers.

---

## 9. Worked Examples (Sketches)

The full worked-example files are a separate work stream (the v1 demo's `examples/` directory). The sketches below show the SDK API exercised in three different modelling regimes, to confirm that the abstractions cover the breadth of the v1 product scope.

### 9.1 Cross-sectional GBDT (the canonical example)

The fully-fleshed example in §2.2.8 + §2.3.7 is the canonical demonstration. It exercises:

- `FeatureSet` with multiple sources, wildcard column selection, explicit fundamental columns, and a forward-return target.
- `Model` subclass implementing `train`, `predict`, and `feature_importance`.
- `Strategy` subclass implementing `positions` with quantile-based long-short selection and weight-unit positions.
- `WalkForwardConfig` with quarterly steps, 3-year sliding window, CPCV with 10 groups.
- `BacktestConfig` with Almgren-Chriss costs, $500M capacity, SPX benchmark, Carhart four-factor decomposition.
- `register()` call wiring everything together with daily 16:30 ET serving.
- Hyperparameter space across `learning_rate` and `num_leaves`.

This example is what `quant init --template gbdt` scaffolds for a new user. It is also the canonical example in the demo narrative's Beat 3 (PRD §3.3).

The auto-generated Dagster asset definition file emitted by `register()` for this example (§3.6) is small and mechanical:

```python
# Generated by quantplatform.register() — do not edit by hand.
from dagster import asset, AssetIn, DynamicPartitionsDefinition
from quantplatform.dagster_glue import platform_asset

FAMILY = "us_equity_long_short_alpha158"

@platform_asset(family=FAMILY, layer="gold")
def gold_us_equity_long_short_alpha158_features(): ...

@platform_asset(family=FAMILY, layer="training", partitions=DynamicPartitionsDefinition(name=f"{FAMILY}_folds"))
def training_run_us_equity_long_short_alpha158(gold_us_equity_long_short_alpha158_features): ...

@platform_asset(family=FAMILY, layer="registry")
def model_version_us_equity_long_short_alpha158(training_run_us_equity_long_short_alpha158): ...

@platform_asset(family=FAMILY, layer="serving", partitions=DynamicPartitionsDefinition(name=f"{FAMILY}_dates"))
def inference_targets_us_equity_long_short_alpha158(model_version_us_equity_long_short_alpha158): ...
```

The bronze and silver asset declarations are folded in by `platform_asset` from the FeatureSet's `sources` and the medallion projection; they are not literally re-emitted per registration. The user never opens this file.

### 9.2 TS forecasting (Nixtla NeuralForecast on a single series)

A univariate forecast model targeting the 5-day-ahead 10-year US Treasury yield, using NHITS from `neuralforecast`:

```python
from quantplatform import (
    FeatureSet, FeatureColumn, Model, Strategy,
    WalkForwardConfig, BacktestConfig, Resources, register,
)
import polars as pl
import pandas as pd  # NeuralForecast is pandas-native; convert at boundary
from neuralforecast import NeuralForecast
from neuralforecast.models import NHITS

ust10y_features = FeatureSet(
    name="ust10y_forecast_v1",
    universe="ust_yield_curve",
    sources={
        "yields": "gold.us_treasury_yield_curve",
        "macro": "gold.macro_indicators_us",
    },
    columns=[
        FeatureColumn("yields", "yield_10y"),
        FeatureColumn("macro", "cpi_yoy"),
        FeatureColumn("macro", "fed_funds_rate"),
    ],
    target=FeatureColumn("yields", "yield_10y_future_5d"),
    entity_columns=["date"],
)

class UST10yModel(Model):
    feature_set = ust10y_features
    resources_train = Resources(cpu=4, memory_gb=16, gpu="T4", gpu_count=1, timeout_hours=4)
    resources_serve = Resources(cpu=2, memory_gb=4)

    def __init__(self, max_steps: int = 1000, input_size: int = 60):
        self.max_steps = max_steps
        self.input_size = input_size
        self._nf: NeuralForecast | None = None

    def train(self, train: pl.DataFrame, val: pl.DataFrame) -> None:
        df_train = train.to_pandas().rename(
            columns={"date": "ds", "yield_10y_future_5d": "y"}
        )
        df_train["unique_id"] = "ust10y"
        self._nf = NeuralForecast(
            models=[NHITS(h=5, input_size=self.input_size, max_steps=self.max_steps)],
            freq="B",
        )
        self._nf.fit(df_train)

    def predict(self, features: pl.DataFrame) -> pl.Series:
        df_pred = features.to_pandas().rename(columns={"date": "ds"})
        df_pred["unique_id"] = "ust10y"
        out = self._nf.predict(df_pred)
        return pl.Series("prediction", out["NHITS"].values)

class YieldDirectionStrategy(Strategy):
    """A degenerate single-asset strategy: long if forecast yield rises, short if falls."""
    model = UST10yModel
    position_units = "weight"

    def positions(
        self,
        predictions: pl.Series,
        universe: pl.DataFrame,
        current: dict[str, float],
    ) -> dict[str, float]:
        forecast = predictions[0]
        current_yield = universe.get_column("yield_10y")[0]
        return {"ust10y_future": -1.0 if forecast > current_yield else 1.0}

register(
    strategy=YieldDirectionStrategy,
    family="ust10y_direction_nhits",
    walk_forward=WalkForwardConfig(
        step="month",
        train_window="5y",
        test_window="1m",
        min_folds=24,
        cv_method="expanding",
    ),
    backtest=BacktestConfig(
        cost_model="fixed_bps",
        cost_params={"bps_per_trade": 1.0},
        capacity_aum_usd=100_000_000,
        benchmark="AGG",
        rebalance_cadence="weekly",
    ),
    serving_schedule="daily 17:00 ET",
)
```

This example exercises:

- A single-entity FeatureSet (`entity_columns=["date"]`).
- A GPU-backed Model (`Resources(gpu="T4", gpu_count=1)`).
- The pandas-conversion-at-boundary pattern for libraries that are not Polars-native.
- An expanding-window walk-forward (vs. sliding in §9.1) appropriate for macro series.

### 9.3 LLM-assisted signal mining (the agentic stub from PRD T6)

PRD T6.1-T6.4 describe an LLM-driven signal-mining workflow as a v1 stretch. The SDK's role in that workflow is the *backtest harness the LLM submits to*. The LLM proposes a feature function, implements it in code, generates a strategy file using the SDK's idioms, and submits via `quant submit`. The SDK does not need any new abstraction for this; the LLM's code is just another quant's code.

What the SDK *does* need is a tag convention for LLM-authored strategies and a discoverable provenance trail. Per PRD T6.4 ("Explicit disclosure in the UI that a feature or model was LLM-authored, with the prompt history attached"), the SDK convention is:

```python
register(
    strategy=LLMProposedStrategy,
    family="llm_research_2026q2_iteration_42",
    walk_forward=walk_forward,
    backtest=backtest,
    description="LLM-authored signal proposal from AlphaGPT iteration 42.",
    tags={
        "authored_by": "llm",
        "llm_model": "claude-opus-4-7",
        "llm_session": "2026-04-21-research-loop-7",
        "human_reviewer": "morgan@morganfund.com",
    },
)
```

The platform reads `tags["authored_by"] == "llm"` and surfaces the LLM-authoring badge in the Models area. The full prompt history is a separate artefact stored alongside the strategy file at submission time, accessed via the LLM session ID lookup. The CLI's `quant submit` accepts a `--llm-prompt-history <file>` flag to attach the prompt log.

This is the v1 scaffolding (T6.1-T6.4). The full agentic loop (T6.2's "closed-loop interface where the LLM proposes a feature function, implements it in code, submits a training + backtest job, and receives the result back for the next iteration") is built on top of this scaffolding by the `worker-llm-research` role; the SDK itself does not run the loop.

---

## 10. What the SDK Explicitly Does NOT Do

This section is the explicit anti-scope. It exists to head off the most common feature-creep requests by naming where the right home is for each capability.

### 10.1 No broker integration

The SDK produces target positions; it does not send orders. The customer's OMS (Order Management System) consumes the published target-position file (§5.11) and is the broker integration point. The platform does not implement FIX connections, REST integrations to brokers, child-order management, or smart order routing. This is decision 8.

The boundary is deliberate. Hedge funds are highly opinionated about execution; the OMS is typically a customer-owned system or a third-party product (Fidessa, Charles River, Trade Mantra, internal builds) the customer has invested in. Integrating with one customer's OMS is per-customer engineering work; integrating with all OMS variants is a multi-year product line of its own. Both are out of scope for v1.

The right home for OMS integration is **a separate platform component, post-v1**, with its own design spec. Reference: `blueprint/positioning/2026-04-21-positioning.md` §6 ("we are NOT a broker integration platform"; implicit in the "infrastructure for managers who already have their own OMS" framing).

### 10.2 No notebook hosting

The SDK is what the notebook *imports*. It is not the editor. The platform's embedded Marimo (or Jupyter-Lab) per PRD §3.3 Beat 3 / OQ-3 is the notebook surface. A user iterating on a strategy in a notebook imports their strategy file and tests `Model.train(...)` and `Strategy.positions(...)` interactively; the SDK provides the abstractions but does not host the notebook server.

The right home for notebook hosting is **the application's notebook embedding** (Chapter 7 §React frontend; PRD §4.1 Beat 3 MUST). Reference: PRD §3.3 Beat 3.

### 10.3 No data-ingestion contracts

The SDK reads from gold; it does not specify how raw data arrives at bronze, how it is transformed to silver, how silver is aggregated to gold. Those are the data platform's concerns (Chapter 8). A FeatureSet declaration assumes the gold table exists; the SDK validates existence at submission time and fails fast if not, but it does not provide a way to *create* the gold table.

The right home for data-ingestion contracts is **Chapter 8 §File contracts and §Inbound ingestion patterns**. Reference: blueprint Chapter 8.

### 10.4 No portfolio optimisation library

The Strategy's `positions()` method returns target positions. The math of constructing those positions — Markowitz mean-variance, Black-Litterman, HRP, robust optimisation — is the user's responsibility. The user imports `cvxpy`, `PyPortfolioOpt`, or rolls their own inside `positions()`.

Per the research synthesis Part 5 §5.2, the platform's *recommended* library set is `cvxpy + custom HRP implementation; PyPortfolioOpt as reference`. The platform pre-installs these in the container image. The SDK does not wrap them.

The argument against wrapping is the same as the argument against wrapping Polars: the user wants the full library API, not a thin shim. The SDK's value-add is upstream and downstream, not at the optimiser boundary.

### 10.5 No backtest engine in user code

The user does not write a backtest loop. The user writes a Strategy; the platform's `worker-backtest` runs the loop. This separation is what makes PBO/DSR computation, capacity sensitivity, and factor decomposition platform defaults rather than user-implemented features.

The right home for the backtest engine is **the `worker-backtest` role + the Polars-based engine** (PRD T1.1, T1.4). The SDK's role is the *configuration interface* (`BacktestConfig`).

### 10.6 No real-time / streaming inference

The serving model is request-response with scheduled inference at daily-or-faster cadence. Sub-second tick-level inference is out of scope per PRD §5 S-1. A user whose strategy requires tick-level execution is in the wrong segment for v1; reference Chapter 14.5 ("we punt to Databricks for petabyte streaming workloads, to specialist HFT platforms for tick").

### 10.7 No multi-tenancy in the SDK

The SDK does not have a tenant concept. The user's strategy file does not declare which tenant it belongs to. The tenant is *the platform deployment* the file is submitted against (Key Idea 1 — silo tenancy: each tenant is a separate GCP project). A quant working at a multi-tenant fund-administration shop is using a different SDK installation per tenant, configured by the deployment's environment.

This is consistent with the silo architecture: the SDK is per-tenant, the user identity is per-tenant, the data is per-tenant. There is no cross-tenant code path in the SDK.

---

## 11. Migration Story

A full Qlib-to-Quant-Platform migration guide is a separate document (`blueprint/sdk/2026-04-21-qlib-migration-guide.md`, planned). This section is the one-page summary the SDK reader needs.

### 11.1 The migration shape

Qlib (Microsoft) is the demo workload (PRD §3.2). The migration is a *port*, not a *re-execution*: the Qlib workflow (data → features → models → validation → serving → audit) is re-expressed as first-class constructs on the Quant Platform, and the resulting SDK strategy file is the canonical example for new users.

The mapping:

| Qlib concept | SDK concept | Notes |
| :--- | :--- | :--- |
| Qlib's data handler (`Alpha158`, `Alpha360`) | `FeatureSet` declaration referencing the platform's gold tables | The platform pre-loads CSI 300 and US-equity Alpha158/Alpha360 as gold tables per PRD Sprint 1. |
| Qlib's `Model` base class | `quantplatform.Model` ABC | Same `train` / `predict` shape; the platform's version is Polars-typed. |
| Qlib's `BaseStrategy` | `quantplatform.Strategy` ABC | The platform's separation of Model and Strategy is sharper than Qlib's; some Qlib "strategies" are actually models, and some are actually strategies, and the migration disambiguates. |
| Qlib's `RollingExpandingTrainSampler` | `WalkForwardConfig(mode="expanding")` | Platform default is sliding; expanding is one config field. |
| Qlib's IC-based evaluation | Built into the `worker-backtest` for cross-sectional models | IC is reported in the BacktestResult alongside Sharpe/PBO/DSR. |
| Qlib's `qrun` config-file workflow | `quant submit my_strategy.py` | The SDK's class-based approach replaces the YAML-config approach (decision 1). |

### 11.2 What the user does

A quant migrating a Qlib LightGBM workflow:

1. Identifies the Qlib data handler and confirms the equivalent gold table is present in the platform (e.g., Alpha158 → `gold.us_equity_alpha158`).
2. Translates the Qlib model class into a `Model` subclass per §2.2. The training code is largely unchanged; the wrapping is different.
3. Decides whether the Qlib "strategy" is actually a Model or actually a Strategy in SDK terms; splits accordingly.
4. Configures `WalkForwardConfig` and `BacktestConfig` with the parameters Qlib was using.
5. Calls `register()` once.
6. Submits via `quant submit`.

The estimated migration time for a single Qlib LightGBM workflow is 2-4 hours for a quant familiar with both Qlib and the SDK. For a Qlib Transformer workflow with custom data handling, 1-2 days.

### 11.3 What the user does *not* do

- Re-implement the model architecture in PyTorch from scratch (the imports are the same).
- Rewrite the feature engineering (the gold tables are pre-populated with Alpha158/Alpha360).
- Build a backtest engine (the platform's engine reads `BacktestConfig` and runs).
- Build an MLflow integration (the platform handles tracking and registry).
- Build a serving wrapper (the `pyfunc` discipline + `Strategy.positions()` is the serving path).

The migration trades Qlib's YAML-driven configuration for Python class-based wiring, and trades Qlib's bundled-but-isolated workflow for an integrated production stack with audit, governance, and serving.

---

## 12. Open Questions and Decisions Deferred to v2

The questions below were surfaced during the spec drafting and are flagged for human decision. None block v1 implementation; each can be resolved as the v1 build progresses or deferred to v2.

**OQ-SDK-1 — Explicit declaration of target horizon on FeatureSet.** §2.4.4 notes that the walk-forward harness's `purge_window` defaults to zero but the recommended value is the target's forward horizon (e.g., 5 days for a `_future_5d` target). The platform currently infers the horizon from the target column name's suffix when present. The question: should the FeatureSet declaration require an explicit `target_horizon` field, removing the heuristic? **Recommendation: yes for v2; keep the heuristic for v1 to reduce friction during pilot.** Decision needed before SDK 2.0.

**OQ-SDK-2 — Pinning wildcard column expansion at submission time.** §2.1.4 notes that `FeatureColumn("alpha158", "*")` expands at extraction time, so a column added to gold after submission is automatically included in the next training run. The question: should the SDK record the expansion at submission time and pin it, requiring a re-submission to pick up new columns? **Recommendation: optional `expected_columns` field on FeatureColumn for v2; defer.** Decision needed before SDK 2.0.

**OQ-SDK-3 — User-forced compute target.** §7.2 maps Resources to cloud targets automatically. Some quants prefer to force the choice (e.g., always use Vertex AI Custom Training even when Cloud Run Jobs would suffice, for consistent observability). The question: should `Resources` accept a `target` field (`Literal["cloud_run", "vertex_ai"]`)? **Recommendation: defer; revisit when a customer asks.** No decision needed for v1.

**OQ-SDK-4 — User-overridable portfolio constructor.** §2.3.7 notes that vol scaling and other portfolio-construction concerns are delegated to the platform's portfolio constructor, configured via Strategy class attributes. The question: should the SDK expose the portfolio constructor as a separately-overridable class (`PortfolioConstructor` ABC) so that a user with a non-standard scheme can implement their own? **Recommendation: yes for v2; v1 ships with the configurable-via-attributes approach.** Decision needed for SDK 1.x evolution.

**OQ-SDK-5 — Refusing zero `purge_window` on forward-horizon targets.** §2.4.5 notes the platform currently warns when `purge_window=0` and the target has a forward horizon, but does not block. The question: should this be a promotion-blocking gate? **Recommendation: yes for v1.x (this is a correctness issue, not a UX issue).** Decision needed before first paid pilot.

**OQ-SDK-6 — Multiple BacktestConfigs per registration.** §2.5.1 notes that v1 supports one BacktestConfig per `register()` call, and that scenario analysis (re-backtest under different cost or capacity assumptions) requires re-registration. The question: should `register()` accept a list of BacktestConfigs (e.g., one per cost-model variant)? **Recommendation: defer to v2.** No decision needed for v1.

**OQ-SDK-7 — Custom hyperparameter selection metric.** §3.3 notes that the validation metric for hyperparameter selection defaults to validation IC for cross-sectional models and RMSE for regression. The question: should `register()` accept a `hyperparameter_metric` argument (a string identifier, or a callable)? **Recommendation: yes for v1.x; the string form covers 95% of cases and is low-risk to add.** Decision needed for SDK 1.1.

**OQ-SDK-8 — Single-best-fold registration vs. ensemble.** §5.8 notes that the `worker-registry` currently registers the single best-performing fold's MLflow run as the production version. The question: should multi-fold ensembles be the default, with the user registering all folds and the serving role calling each and averaging? **Recommendation: defer to v2; v1 single-best-fold is the simpler default and matches PRD scope.** Decision needed before SDK 2.0.

**OQ-SDK-9 — Per-strategy `pip install` overlays.** §7.4 notes that the platform's container image is the dependency manifest; users cannot add packages per-strategy. The question: should the SDK support per-strategy package overlays (e.g., a `requirements_extra.txt` colocated with the strategy file)? **Recommendation: defer to v2; v1's central dependency model is the parity guarantee.** Decision needed for SDK 2.0.

**OQ-SDK-10 — Asynchronous training APIs.** The current `Model.train(train, val)` is synchronous and blocking. Some advanced workflows (active learning, online learning) want to invoke training as a streaming process. The question: should the SDK support an async variant? **Recommendation: defer to v2; the synchronous API covers all v1 scope.** No decision needed for v1.

**OQ-SDK-11 — Exposing the Dagster asset graph at the SDK level.** §3.6 and §6.7 specify that `register()` translates the StrategySpec into a Dagster asset definition file, that the asset names are deterministic, and that the user does not author Dagster code in v1 (quants write `Model.train` and `Strategy.positions` only; the platform writes the assets). The question: should the Dagster asset graph be exposed at the SDK level — i.e., should a power-user quant be allowed to write `@asset` directly to extend the auto-generated graph with a custom node — or should it remain a platform implementation detail? **Recommendation: hidden in v1 (the parity guarantee and the audit story are easier to defend when the asset graph is platform-owned); v2 may expose `@asset` for power users with a clear escape hatch and corresponding governance.** Decision needed for SDK 1.x evolution.

These are the questions the spec author identified. Reviewers may surface additional questions during the architecture review; they will be added to this list before sign-off.

---

## Appendix A — Full canonical example

The canonical strategy file from the spec brief, reproduced here as a complete artefact for the implementer:

```python
from quantplatform import (
    Strategy, Model, FeatureSet, FeatureColumn,
    WalkForwardConfig, BacktestConfig, Resources,
    register,
)
import polars as pl
import lightgbm as lgb

features = FeatureSet(
    name="us_equity_alpha158_v1",
    universe="us_equity_top_1000",
    sources={
        "alpha158": "gold.us_equity_alpha158",
        "fundamentals": "gold.us_equity_fundamentals",
    },
    columns=[
        FeatureColumn("alpha158", "*"),
        FeatureColumn("fundamentals", "log_market_cap"),
        FeatureColumn("fundamentals", "book_to_market"),
    ],
    target=FeatureColumn("alpha158", "label_return_5d"),
)

class AlphaModel(Model):
    feature_set = features
    resources_train = Resources(cpu=8, memory_gb=32)
    resources_serve = Resources(cpu=2, memory_gb=4)

    def __init__(self, learning_rate: float = 0.05, num_leaves: int = 64):
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self._lgb = None

    def train(self, train: pl.DataFrame, val: pl.DataFrame) -> None:
        ...

    def predict(self, features: pl.DataFrame) -> pl.Series:
        ...

class LongShortStrategy(Strategy):
    model = AlphaModel

    def positions(
        self,
        predictions: pl.Series,
        universe: pl.DataFrame,
        current: dict[str, float],
    ) -> dict[str, float]:
        ...

register(
    strategy=LongShortStrategy,
    family="us_equity_long_short_alpha158",
    walk_forward=WalkForwardConfig(
        step="quarter",
        train_window="3y",
        test_window="1q",
        min_folds=8,
    ),
    backtest=BacktestConfig(
        cost_model="almgren_chriss",
        capacity_aum_usd=500_000_000,
        benchmark="SPX",
    ),
    hyperparameter_space={
        "learning_rate": (0.01, 0.1, "log"),
        "num_leaves": (16, 256, "int"),
    },
    serving_schedule="daily 16:30 ET",
)
```

This is the artefact a quant submits via `quant submit alpha_strategy.py`. Every section of this spec should be readable as describing what the platform does with that file.

---

## Appendix B — Glossary

- **`register()`** — the single platform wiring function; the only SDK call that has platform-side side effects.
- **Family** — a strategy family identifier; groups related registrations under a single MLflow registered model name.
- **Fold** — one out-of-sample window in a walk-forward evaluation; corresponds to one MLflow run.
- **CPCV** — Combinatorial Purged Cross-Validation; the platform's default cross-validation method per López de Prado, *Advances in Financial Machine Learning*, 2018, Ch. 7.
- **PBO** — Probability of Backtest Overfitting; a López de Prado measure computed automatically by `worker-backtest` per Bailey-López de Prado 2014 / *AFML* Ch. 11.
- **DSR** — Deflated Sharpe Ratio; the headline Sharpe adjusted for the multiple-testing trial count, per Bailey-López de Prado 2014.
- **Pyfunc** — MLflow's standard model packaging flavour; captures both the serialised model and the inference wrapper code (Chapter 9 §Model packaging).
- **Gold layer** — the curated, business-shaped data layer in the medallion architecture (Chapter 8 §Gold).
- **`as_of`** — the system-time timestamp used as the cutoff for `_knowable_at` filtering; the bi-temporal correctness gate (Chapter 8 §Point-in-time correctness).
- **Bi-temporal columns** — `_knowable_at` (system time), `_valid_from`/`_valid_to` (business time); the schema discipline that prevents look-ahead bias (Chapter 8).
- **Quant** — quantitative researcher / engineer at a hedge fund customer; the SDK's primary user.
- **Operator** — vendor staff running the platform; uses the CLI and admin UIs.
- **Strategy file** — the Python file the user writes against the SDK; submitted via `quant submit`.

---

*End of SDK design specification.*
