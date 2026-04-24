# Model Training and Serving

## Separation of training and serving

The platform cleanly separates model training — a compute-heavy, often long-running, sometimes GPU-dependent activity — from model serving — a latency-sensitive, always-on, request-response activity. Both are first-class capabilities of the platform, but they run on different infrastructure with different scaling characteristics and different deployment cadences.

![ML training and serving pipeline](diagrams/rendered/06-ml-pipeline.pdf){width=95%}

## Training environment

### Workload characteristics

Training jobs in a quantitative context fall into three categories, each with different infrastructure needs:

1. **Feature engineering and small-model training** — minutes to hours, CPU-only, memory-bound. Examples: linear factor models, tree-based risk scoring, rolling-window statistics. Runs comfortably on Cloud Run Jobs with 4–16 vCPU and 16–64 GB of memory.

2. **Medium deep learning** — hours to a day, single GPU, occasionally multi-GPU. Examples: LSTM price predictors, transformer-based signal generators, autoencoders for anomaly detection. Requires GPU-enabled compute: either Cloud Run with GPU (limited regions), GKE Autopilot with a GPU node, or Vertex AI Custom Training.

3. **Large-scale training and hyperparameter search** — days, multi-GPU, distributed. Uncommon in traditional quant but relevant for firms exploring foundation-model approaches. Requires Vertex AI Training with multi-worker configurations or GKE with dedicated GPU pools.

The platform dispatches to the appropriate compute target based on job metadata. Small jobs stay inside the main application's Cloud Run service (a synchronous or short async training). Medium and large jobs are submitted as Cloud Run Jobs, GKE jobs, or Vertex AI Custom Training jobs and tracked asynchronously.

### Training orchestration

A training run is a first-class aggregate in the domain model. It carries:

- The model identity and version being trained
- The input dataset version (a pinned snapshot of gold-layer data)
- The training configuration (hyperparameters, loss function, validation split)
- The target compute environment
- The lifecycle state (submitted, running, evaluating, completed, failed)
- Metrics (loss curves, validation scores, backtest results)
- Artefact references (model weights, evaluation reports, serialised pipelines)

Training is triggered through the `/training/runs` API endpoint. The handler records a `TrainingRunSubmitted` event, dispatches the compute job to the target environment, and returns a run identifier. A background worker polls the compute environment for status and emits events on lifecycle changes.

The training pipeline itself is orchestrated by Dagster (introduced for the data layer in the previous chapter and reused here). A `training_run` is a dynamic Dagster asset per strategy, with the gold-layer assets it consumes as upstream dependencies; a `model_version` is the downstream asset that materialises when training completes, validation gates pass, and the artefact is registered in MLflow. The asset-check model carries the platform's validation gates — point-in-time correctness checks, walk-forward thresholds, calibration tests — so a model that fails validation cannot become a materialised `model_version` asset. The same lineage view that traces gold aggregates back to bronze files extends one more hop to show which `training_run` consumed which gold snapshot to produce which `model_version`. The SDK's `register()` call translates a strategy specification into the corresponding Dagster asset definitions; researchers do not write Dagster code by hand.

The actual training code runs in the same container image as the main application. A dedicated training entrypoint selects the training module by job type, loads the pinned dataset, executes the training loop, logs metrics and artefacts to MLflow, and exits. This means the training environment is testable locally: the same entrypoint runs in docker-compose with a small dataset and produces a real MLflow run.

### Data extraction and reproducibility

Training data is extracted from gold-layer tables with an explicit `as_of` timestamp. The extraction query, its result hash, and the `as_of` are all recorded in the MLflow run. A training run can be reproduced at any later date by re-extracting with the same `as_of`, the same query, and confirming the hash matches.

Bi-temporal correctness (see the data platform chapter) guarantees that corrections to historical data after the original training date do not contaminate reproductions.

### Point-in-time correctness and look-ahead bias

The quantitative-finance literature consistently identifies look-ahead bias — the inadvertent use of information that would not have been available at the decision time being simulated — as a leading cause of quantitative strategies appearing profitable in backtests and failing in production (López de Prado, *Advances in Financial Machine Learning*, Wiley 2018, Ch. 11–13; Bailey & López de Prado, "The Probability of Backtest Overfitting," *Journal of Computational Finance*, 2014). A representative example: a consumer credit-card transaction occurs on Monday, is aggregated by the data vendor on Wednesday, and arrives in the customer's data lake on Thursday. A naive backtest attributes the transaction to Monday and trades off it. A correct backtest attributes it to Thursday, when it was actually knowable, and obtains materially different results.

The platform enforces point-in-time correctness as a pipeline property, not as a researcher's discretionary practice. Every silver and gold table carries a `_knowable_at` column (system time — when the row became visible to the platform) alongside `_valid_from` / `_valid_to` columns (the business-time interval over which the datum applies); both are distinct from the original business-event timestamp. Every training extraction query filters by `_knowable_at <= :as_of`; queries lacking this filter fail validation at pipeline build time and cannot ship to production. The Data Platform chapter documents the column scheme in full.

### Walk-forward validation

A single train-test split against historical data is insufficient evidence of a model's production viability. The platform's validation harness implements walk-forward validation as a first-class operation: the training window is advanced through historical time in steps, the model is retrained at each step with strictly pre-step data, and performance is measured on the next step's out-of-sample period. The result is a sequence of out-of-sample performance observations rather than a single retrospective number, and it is dramatically more predictive of live-trading outcomes.

Walk-forward validation is a gating criterion on model promotion. A model whose walk-forward performance fails the configured threshold cannot transition from staging to production in the MLflow registry, regardless of the developer's preferences. This is a platform rule, not a team convention.

### Research-to-production code parity

The second structural cause of backtest-to-production failure is code divergence between the researcher's notebook and the production pipeline: a feature computed one way in research and a different way in production. The platform collapses this divergence by requiring that the feature-extraction code used at training time is the same callable used at serving time, packaged into the model's `pyfunc` wrapper and invoked identically in both contexts. Research notebooks import the same wrapper module when prototyping, making the notebook the draft of the production serving path rather than a parallel artefact.

## MLflow as the model registry and tracking backbone

The platform uses MLflow as the experiment tracking, model registry, and artefact storage coordinator. MLflow is open source, runs fully locally in docker-compose, and is backed by Postgres and GCS — both components already in the stack.

The MLflow tracking server is deployed as a separate Cloud Run service per tenant. It shares the Postgres instance with the main application (distinct schema) and uses the tenant's GCS bucket for artefact storage. Its upgrade cadence is decoupled from the main application for MLflow application versions — MLflow releases move slowly and are low-risk, whereas the application ships features continuously. The decoupling does not extend to the Postgres engine version itself: a Postgres major-version bump or an extension change requires coordination across both consumers and is managed at the tenant-upgrade level. Such changes are rare.

### Experiments, runs, and models

MLflow's concepts map cleanly onto the platform's vocabulary:

- **Experiment** — a named grouping of related training runs for a given model family
- **Run** — a single execution of a training pipeline, containing logged parameters, metrics, and artefacts
- **Registered model** — a named model with a version history
- **Model alias** — a mutable pointer (e.g. `staging`, `production`, `champion`, `challenger`) attached to a specific version of a registered model

The platform's domain uses the Model aggregate as the user-facing entity and maps its lifecycle operations onto MLflow registry calls. A user clicking "promote to production" on a model version triggers a domain command that moves the `production` alias to that version and emits a `ModelPromoted` event. The platform pins MLflow at version 2.16 or later (where Model Aliases are first-class and Model Stages are deprecated) and follows the alias-based lifecycle rather than the deprecated stage transitions; migration to MLflow 3.x, which removes stages entirely, is a non-disruptive engine upgrade because the platform never relied on stages.

### Model packaging

Models are packaged using MLflow's `pyfunc` flavour, which captures both the serialised model and its inference wrapper code. The wrapper is responsible for feature transformations, input validation, and output shaping. This means the serving code is part of the model artefact, not part of the serving infrastructure. Upgrading a model cannot break the serving endpoint's calling contract.

## Serving

### Inference modes

The platform supports three serving modes, all exposed through the application's REST API:

- **Synchronous inference** — a single request carrying a feature vector or identifier, returning a prediction within a few hundred milliseconds. Endpoint: `POST /serving/{model-name}/predict`.

- **Batch inference** — a request referencing a dataset (by ID) or a file (by GCS URI), returning a job identifier. Results are written to a caller-specified GCS location or made available through a subsequent query endpoint. Suitable for end-of-day scoring, portfolio-wide risk calculation, or backtest sweeps.

- **Scheduled inference** — a recurring pipeline configured at the model level, producing outputs on a cadence (e.g. daily post-close predictions). Scheduled runs are tracked in the `pipeline_runs` table alongside data pipelines.

### Serving architecture

Serving endpoints are handlers within the main application process. On startup, the serving module reads a registry of models carrying the `production` alias from MLflow, downloads each model to a local cache directory, and holds references in memory. Requests are dispatched to the appropriate model by name and version.

This avoids the complexity of a separate model-serving service (Triton, BentoML, Seldon) at the cost of coupling model updates to application restarts or to a lazy-reload mechanism. For the quantitative hedge-fund target market — where request volumes are modest, models are updated daily or weekly rather than continuously, and latency requirements are in the tens of milliseconds rather than sub-millisecond — this coupling is acceptable.

A lazy-reload mechanism watches for `ModelPromoted` events on the event bus and triggers a per-process reload of the promoted model, with the old version retained in memory until the in-flight requests drain.

### High-throughput or GPU-bound serving

When a specific model's serving requirements exceed what the main application process can handle — GPU inference, QPS beyond a few hundred, or strict isolation — the same container image is deployed as a dedicated Cloud Run service with an environment variable selecting a serving-only entrypoint. The routing URL for that model is updated in the application's model registry, and subsequent requests flow directly to the dedicated service.

No separate codebase, no separate build pipeline, no separate deployment — only a second Cloud Run service running the same image with a different entrypoint.

### Inference auditability

Every inference request and response is logged to an `inference_log` table with timestamp, user, model name, model version, input feature hash, output, and latency. This log is the auditable trail that connects a business decision (informed by an inference) back to the model, training data, and code that produced it.

For regulated customers, the inference log is retained alongside the event store with the same durability guarantees and is exportable on demand.

## Feature extraction reuse

Features used at training time must match those used at serving time — the classic train-serve skew problem. The platform addresses this by packaging feature extraction code into the `pyfunc` wrapper of each registered model. The same Python callable that computes features from a silver-layer row at training time is invoked at inference time.

For customers who need a full feature store (shared features across models, online/offline sync, time-travel feature queries), Feast is the portable, fully-local-compatible recommendation and can be layered on without disturbing the rest of the stack. It is not in the default scope because quantitative hedge funds typically maintain their feature pipelines inside their model code rather than externalising them.
