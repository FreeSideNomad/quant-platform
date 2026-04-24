# Design Brief

## What this blueprint is

A reference architecture for building a multi-tenant Software-as-a-Service platform that enables quantitative hedge funds to productionalise their trading models. It covers the end-to-end stack: a React user interface, a Python application exposing a REST API, authenticated against customer-managed enterprise identity providers, a data ingestion and transformation platform, a model training environment, a model serving surface, and the supporting infrastructure, deployment, and operational tooling.

The blueprint is opinionated. It favours a small number of well-understood components over a large number of novel ones, and it requires that the entire system can be run and exercised on a developer laptop in a faithful simulation of production.

## Who this platform is for

Quantitative investment firms — systematic hedge funds, multi-strategy shops, and quantitative arms of larger asset managers — whose internal teams build predictive, risk, or execution models but lack the engineering substrate to move those models from research notebooks to production-grade services. The platform provides the engineering foundation these customers cannot or will not build in-house, while ceding to them full control over their data, identity, and deployment environment.

Current industry research makes this market framing concrete. Equity market neutral, quant multi-strategy, and global macro have been among the most-favoured quantitative strategies in successive industry capital-introduction surveys entering 2026. Separately managed accounts — structures in which a single institutional investor receives a dedicated, customised implementation of a manager's strategy — are a substantial and growing share of how managers serve large allocators, and they push managers towards deployment patterns that can stamp out dedicated instances per mandate. Leading quantitative managers publicly describe their engineering edge in terms of model governance (versioned inventories of models with documented inputs, signals, and validation artefacts) and strict separation between research, development, and production environments; published accounts of internal developer platforms at large quant managers describe model-to-production workflows reduced from weeks of manual handover to minutes through a configuration-driven golden path. The architectural assumption in this blueprint — that each customer receives a dedicated silo that their own quants can push models into through a standardised, audited workflow — aligns directly with where this segment is moving.

Typical users within a customer organisation fall into four personas:

- **Quant developers** who train, version, and promote models
- **Risk and compliance officers** who inspect model behaviour and audit trails
- **Operations engineers** who monitor data pipelines, model performance, and infrastructure
- **Platform administrators** who manage users, roles, and tenant configuration

## Goals

1. **Faithful local simulation of the production *workflow*.** Every production *behaviour* is reproducible on a single developer machine via docker-compose — auth flow, ingestion, CQRS event loop, model-training entrypoint (small data + small model), inference serving, audit. The slogan is "the same code path runs locally and in the cloud, validated end-to-end," not "production runs on your laptop." Production-scale training compute (deep-learning jobs, hyperparameter sweeps, GPU-bound work) explicitly runs on managed cloud (Cloud Run Jobs, Vertex AI Custom Training); the developer launches it with one command from the local environment, the *job* runs in the cloud. This is the governing constraint for the development workflow; every architectural decision is evaluated against it.
2. **Silo tenancy.** Each customer receives a dedicated instance of the platform, either in the vendor's GCP organisation or the customer's own (BYOC). Data never crosses tenant boundaries.
3. **Enterprise identity federation.** Customers bring their existing Google Workspace or Microsoft Entra directories. The platform does not maintain its own user store.
4. **Portable open-source components.** Where a managed cloud service and a portable open-source component are both viable, the open-source component wins unless the cost of running it is unjustifiable.
5. **Postgres-centric data plane.** Operational state, event sourcing, message queueing, time-series data, and graph data all live in Postgres via extensions. Blob storage for raw artefacts is the only exception.
6. **Near-monolithic application.** One codebase, one Docker image, one test suite, one mental model — deployed as a small set of single-purpose services (the API, projectors, pipeline workers, training and inference workers, the scheduler) selected at startup by an environment variable. Workers scale independently of the API, but share the build, test, and release pipeline.
7. **Continuous delivery with safe rollouts.** Every change is built, tested, and promoted through staged environments with blue/green traffic splitting and instant rollback.
8. **Per-tenant operability.** Each instance is independently observable, upgradable, and billable. Fleet operations scale to hundreds of tenants through a thin control plane, not through per-tenant heroics.

## Design principles

| Principle | Implication |
| :--- | :--- |
| Local-first | Any service added to production must have a local equivalent; otherwise it is not used |
| Less is more | One Postgres with extensions, one application process, one CI/CD pipeline |
| Boring technology | Proven, widely-supported components with strong communities and documentation |
| Event-sourced by default | State is derived from an append-only event log; read models are projections |
| Silo over pool | Tenant isolation comes from separate deployments, not row-level filters |
| Forward-compatible migrations | Schema changes are additive; blue/green deploys never require synchronous migrations |
| Code is the contract | Event schemas, API contracts, and infrastructure live in version control and are tested |

## Non-goals

- Freemium, self-serve, or small-business tiers. The floor cost of silo tenancy makes these economically unviable.
- A managed research environment. The platform productionalises models; it does not replace Jupyter, notebooks, or research clusters.
- A trade execution venue, order management system, or custody solution. The platform consumes and produces data; it does not route orders or hold positions.
- A general-purpose machine learning platform. The architecture is tuned for quantitative finance workloads: point-in-time correctness, deterministic reproduction, audit traceability.
- Real-time algorithmic trading with sub-millisecond latency requirements. The serving model targets batch and near-real-time inference; ultra-low-latency paths require specialised infrastructure outside this blueprint.

## Success criteria

A new engineer clones the repository, runs a single command, and has a working local instance with seeded data in under fifteen minutes. The integration test suite runs the full stack without touching cloud resources. A new tenant is provisioned from a single operator action and is live within thirty minutes. A release candidate is promoted to production with a blue/green traffic shift that can be rolled back in seconds. A model trained by a customer on Monday is running in production inference by Tuesday with a full audit trail linking the inference output back to the training data.
