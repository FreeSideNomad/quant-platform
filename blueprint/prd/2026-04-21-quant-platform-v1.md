---
title: Quant Platform v1 — Product Requirements Document
date: 2026-04-21
status: draft
template: pmprompt prd-writer (pmprompt.com) adapted for context
inputs:
  - blueprint/src/*.md (platform architecture)
  - blueprint/research/2026-04-21-modern-quant-synthesis.md (research synthesis)
grounded_in: >
  The research synthesis's "7 gaps in the blueprint" + the user's stated goal
  ("strong visual impactful UI something hedge fund managers can truly use")
  + the memory that Microsoft Qlib is the planned reference workload.
audience: internal (platform team) — this is the build brief, not the marketing narrative
---

# Quant Platform v1 — Product Requirements Document

The demoable v1 of the Quant Productionalization Platform: the version that converts "generic tech tool that runs models" into "the artefact a hedge-fund manager and an LP allocator would both look at and recognise as a credible modern quant substrate."

---

## 1. Problem Statement

### 1.1 Current situation

The platform as documented in the blueprint (`blueprint/src/*.md`) is architecturally sound. It has tenancy, auth, data platform, ML platform, infrastructure, CI/CD, observability, security, and a phased roadmap. The underlying architectural decisions — silo tenancy, Postgres-centric operational substrate, single-image-multi-role, CQRS, research-to-production code parity, local-first development — are consistent, internally coherent, and well-argued.

What the platform *does not yet have* is the thing a hedge-fund customer would touch, show a colleague, and describe in a sentence. It has the substrate; it does not have the product. The closest description a visitor to the blueprint could give today is "it's a generic multi-tenant Python + Postgres + Cloud Run platform that can run ML models." That description is technically accurate and commercially fatal. Every credible competing narrative — "it's the internal developer platform that Man Group built for its own quants and now sells," "it's the Jenny-Lin-style hedge-fund quant-productionalization platform," "it's the reference architecture Microsoft uses for Qlib" — has a **concrete workload**, a **specific workflow the user walks through**, and a **user interface that looks like it was designed for the audience, not for an engineer**. The current platform does not.

#### Competitive context

This v1 is being built into a market that already has credible incumbents and credible alternatives. The full head-to-head competitive map lives in `blueprint/src/14.5-comparison-to-alternatives.md`; the positioning argument lives in `blueprint/positioning/2026-04-21-positioning.md`. The two compressed facts the PRD reader needs to internalise:

- **The closest direct competitor is SigTech** (London, Brevan Howard spinout 2019, customers with $5T+ combined AUM, just launched MAGIC AI-agent layer in 2025). They are quant-purpose-built, hedge-fund-native, and six years more mature than us. We do not beat them on maturity, brand, or data depth. We beat them on three specific axes: silo + BYOC tenancy (their public posture is multi-tenant cloud SaaS), open-source-first stack (they are proprietary), and mid-market price point (they are enterprise-tier).
- **Generic enterprise MLOps competitors** (Domino Data Lab, Databricks, Palantir Foundry/AIP) are capable but not quant-native. A customer adopting any of them for a quant workflow would spend months integrating PBO/DSR, walk-forward enforcement, bi-temporal data, and audit-chain implementations that this platform provides as defaults. We win on quant-specificity; we lose on platform breadth and enterprise sales motion. We do not contest the multi-domain enterprise segment.

V1's demo and UI must therefore make the three differentiators visible *as the customer scrolls through the UI*, not just visible in the marketing collateral. The hero screens identified in §4.3 are the surface that has to carry the differentiation: silo isolation visible in the data-source view, open-source-stack legible in the runtime metadata, and quant-native defaults (PBO/DSR/walk-forward/bi-temporal) exposed as first-class platform concepts in the validation and lineage views. A demo that does not embody the differentiation cannot be saved by a sales pitch that asserts it.

#### What v1 specifically must address

The research synthesis (`blueprint/research/2026-04-21-modern-quant-synthesis.md`) identifies seven specific capability gaps that would close the credibility distance between the current blueprint and a modern-quant audience's expectations: first-class backtest-as-a-service with PBO/DSR defaults, walk-forward validation enforced at the platform layer, distributional model outputs, LLM-based signal-mining infrastructure, regime detection as a cross-cutting service, a reconsidered feature-store trigger, and named alternative-data ingestion patterns. Not all seven are v1-scope; some are Phase-3 or later. The PRD selects the subset that must land in v1 to make the demo credible.

#### Pricing and segment assumption (informs v1 demo audience)

For the demo audience and the v1 design decisions, the pricing assumption is a **Professional tier at $300-400k/year** targeting **mid-market hedge funds in the $500M-$5B AUM band**. This anchors:

- Demo pacing and depth: the audience has technical sophistication and is qualified to evaluate the platform's specifics.
- UI register: financial-professional, dense, dark-mode-default; not consumer-grade.
- Sales motion: self-serve trial + paid pilot + annual contract; not enterprise consulting.
- Build-vs-buy framing: "you have under 25 engineers and your CTO is overcommitted; building this yourselves is 18-30 months."

These pricing and segment assumptions are provisional and tested in the first three pilots; see `blueprint/positioning/2026-04-21-positioning.md` §7 for the full pricing structure including Starter ($150-200k) and Enterprise ($500-800k+) tiers.

### 1.2 User pain points

Two user types feel two distinct versions of this pain.

**The hedge-fund quant/engineering lead** (primary user, paying customer):

- They are running a Python monorepo that grew organically over four years. The research notebooks and the production deployment drifted apart years ago; nobody on the team can tell you precisely which notebook produced which live model. Every new strategy takes three months from research to production, and most of those three months are engineering overhead that has nothing to do with the research idea.
- Their data discipline is uneven. Some silver tables have point-in-time timestamps; others don't. Some data vendor restatements overwrite prior values; others append. Their backtests are silently contaminated by look-ahead bias in ways that are hard to detect and impossible to audit.
- Their compliance posture is "we have logs" — which is not enough to satisfy a 2026 ODD questionnaire from a sophisticated LP, let alone an actual regulator. They know they need model governance, cryptographic audit chaining, immutable inference logs; they have not built them because the team's focus is signal research.
- They have heard about foundation models and LLM-based signal mining. They would like to try AlphaGPT-style workflows. They do not have the engineering headcount to build that infrastructure themselves.
- A competing platform vendor has started making credible noises. Their own head of platform has been pitching an internal rewrite. The quant lead is looking for a third option: buy the substrate, keep the research differentiation.

**The LP allocator running operational due diligence on a manager** (secondary user, validator):

- They have a 2026 ODD questionnaire with specific technology-discipline questions: "Describe your point-in-time data discipline. Describe your walk-forward validation protocol and how it's enforced. Describe your model-registry audit trail. Describe what would happen to your production deployment if your CTO left tomorrow." The managers they interview give uneven, often embarrassed answers.
- They would like to see a platform a manager uses, not just hear about it. The platforms they have seen are research-grade (Jupyter notebooks stitched together with bash) or infrastructure-grade (Kubernetes manifests and Airflow DAGs). They have not seen a platform that *looks like a product* and that answers their questionnaire questions in its user interface without the manager having to narrate over a screenshare.
- When a manager can show them a model lifecycle view with an immutable audit trail, a model promotion flow with a PBO/DSR gate, and a data-lineage view showing how a specific inference output traces back to specific bronze source files, the allocator's diligence conversation shortens from ninety minutes of interrogation to thirty minutes of validation. That shortening is worth real money in deal velocity.

### 1.3 Business impact

The impact of not addressing this is concrete and quantifiable.

- **Deal velocity.** The user is in active conversations with Jenny Lin (peer founder with a parallel hedge-fund productionalization product) and with the Morgan Stanley contact introduced via Jenny. Neither conversation advances beyond "interesting" without a demo artefact. Every further meeting the user takes on the current substrate spends social capital without producing commitment.
- **Market timing.** The SMA-driven deployment pattern and the AI-first-hedge-fund narrative (Man Group's public AlphaGPT disclosure, the agentic-quant thread in 2025-2026 research) are creating a window for platform vendors. The managers who will adopt externally-provided substrate in the next 12-24 months are the ones who are making the build-vs-buy decision *now*. A demo artefact in front of them now converts; the same demo in 18 months converts less.
- **Narrative defensibility.** A generic "multi-tenant Python platform" has no moat. A platform with a specific quant-productionalization story — demo workload, hero UI, research-driven capability set — is defensible against a generalist cloud-SaaS competitor and legible to a quant customer.

The PRD aims at all three. The v1 demoable product is specifically the artefact that makes the Jenny Lin and MS contact conversations advance; that, in turn, seeds the LP-allocator and customer conversations that the underlying business needs.

---

## 2. Target Users

### 2.1 Primary persona — Morgan, Head of Quant Technology at a mid-sized systematic equity shop

Morgan runs engineering for a 50-person systematic equity fund with $2B AUM. The fund's alpha research is done by 20 quants (PhDs, ex-academics, some ex-banks) working in a shared Python monorepo. Morgan's team of 8 engineers is responsible for everything from data pipelines through backtesting infrastructure through production deployment.

**Morgan's world:**

- Runs daily end-of-day retraining on ~30 production models.
- Ingests 12 data vendors, including 3 alternative-data vendors whose restatements happen without warning.
- Maintains an internal MLflow deployment, an internal Airflow for pipelines, an internal Jenkins for deploys, an internal hand-rolled monitoring stack.
- Has two open CTO-level headcount reqs that have been unfilled for 9 months.
- Knows the team would be faster with less infrastructure to maintain, and has an authorisation from the CFO to spend up to $400k/year on an external platform if it credibly replaces 40% of what the team currently builds.

**Morgan cares about:**

- **Research-to-production velocity.** Every week shaved off the feature-idea-to-live-model loop is worth more than any single alpha improvement.
- **Audit-readiness.** Compliance has asked for model governance for two years. Morgan has not delivered it. The LP's ODD questionnaires are getting sharper every cycle.
- **Hiring leverage.** A platform that a new quant hire can be productive on in week one instead of month three is worth paying for.
- **Not being locked in.** Whatever Morgan buys must use open-source components where possible; the codebase, models, and data must be portable back out.

**Morgan will adopt** if: a demo walks through a realistic workflow end-to-end in under 30 minutes; the demo includes a credible answer to each of the LP's ODD questions; the platform's local-dev story is compelling enough that Morgan's team can experiment with their own data in a day.

**Morgan will reject** if: the demo is a slide deck; the workflow requires manual narration to hold together; the platform demands an immediate rewrite of Morgan's existing code; the architecture assumes Morgan uses AWS and Morgan is GCP-native.

### 2.2 Secondary persona — Priya, Senior Investment Analyst running ODD on a manager

Priya works for a $30B endowment and leads the operational due-diligence workstream on quant managers being considered for allocation. She meets 20-30 quant managers a year and runs ODD on 8-12 of them.

**Priya's world:**

- Has an 11-page ODD questionnaire specifically for systematic managers.
- Four of those pages are technology and data-discipline questions.
- Typically runs a two-hour ODD session per manager, sometimes on-site.
- Makes a recommendation to her endowment's investment committee that, if accepted, translates to a $25-150M allocation.

**Priya cares about:**

- **Evidence, not assertions.** Every question in her questionnaire wants documented evidence. "We have point-in-time data discipline" is an assertion; a UI that shows a specific silver-layer row with its `_knowable_at`, `_valid_from`, `_valid_to` columns and a lineage link to the bronze file it came from is evidence.
- **Managerial competence.** Priya reads the manager's technology the same way she reads their trade blotter — as a revealed preference. A disciplined manager has a disciplined tech stack.
- **Defensibility over time.** A manager who has built on vendor X is exposed to vendor X going away. A manager on open-source-first substrate is less exposed.

**Priya will nod** if: the manager walks through their workflow using an interface that clearly was not built for her benefit (i.e., it's their daily tool, not a pitch deck); the interface answers her questionnaire questions without the manager having to narrate; the manager can produce a specific historical inference from 18 months ago with full lineage in under 60 seconds.

**Priya will flag** if: the manager struggles to find a specific historical inference; the manager's answers to data discipline rely on "our researchers know to..."; the manager cannot show a model promotion history.

### 2.3 Operator persona — the user (platform builder)

Not a customer; the user themselves as the platform operator. Relevant because v1's internal operability matters for running demos.

**What the operator needs:**

- A one-command path from a git clone to a running demo with seeded data.
- A set of demo scripts that replay a canned narrative (data ingest → model train → backtest → promote → serve → inspect) reliably, for live demos and for recorded NotebookLM video input.
- A way to iterate the demo itself (add a new screen, rewrite a narrative beat) without rewriting the underlying platform.

### 2.4 Anti-personas (explicit exclusions for v1)

- **Retail systematic traders.** The floor cost of silo tenancy is too high; freemium / self-serve is out of scope per the blueprint's design brief.
- **HFT / market-making desks.** Their latency requirements are outside the platform's serving profile.
- **Crypto-native quant funds.** Many of the patterns transfer, but custody, on-chain data, and regulatory disposition are different enough that treating them as a variant of equity quant misleads.

---

## 3. Proposed Solution

### 3.1 Overview

Quant Platform v1 is a demoable, internally coherent instance of the platform that makes the abstract blueprint concrete through one specific **demo workload** — a Qlib-style cross-sectional equity alpha workflow on a synthetic universe — dressed in a **hero UI** that shows what running the platform feels like. The workload and the UI together turn the blueprint from architecture into product.

The demo workload is not itself the product; no customer buys a demo pipeline. The workload is the *narrative spine* that walks a viewer through every layer of the platform: data ingestion, silver/gold transformation, point-in-time discipline, feature engineering, baseline GBDT training, walk-forward validation with PBO/DSR, model registry and promotion, serving, audit trail, and LP-facing reporting. Every capability the PRD asks for is motivated by the workload; every screen in the UI corresponds to a beat in the workload's narrative.

The three priorities of v1, in order:

1. **The demo narrative works end-to-end.** A viewer watching a 30-minute live walkthrough (or a NotebookLM-generated video of the walkthrough) follows a single coherent story from data arriving to an LP-facing report being produced, with no unexplained gaps.
2. **The UI is hedge-fund-manager-grade.** Not "clean and functional" in the engineering sense, but visibly designed for the financial professional audience: dense information, dark-mode-by-default, financial-terminal aesthetic cues, fast-loading, no animation gimmicks.
3. **The substrate matches the claims.** Every capability the narrative claims must actually work on the substrate. If the demo says "here's the bi-temporal lineage of this inference," clicking the link actually shows the lineage pulled from real Postgres data, not a mocked screenshot.

Priority 3 constrains priority 1 constrains priority 2 — we do not demo capabilities we have not built, but we do build capabilities the demo narrative requires.

### 3.2 Demo workload — Qlib-style cross-sectional alpha workflow

The demo workload implements a Qlib-style cross-sectional equity alpha workflow on the Quant Platform. The original PRD specified CSI 300 daily bar data, Alpha158/Alpha360 feature sets, and advanced Transformer models (iTransformer/MASTER) as the v1 demo. **MVP-A delivers a narrower but honest implementation:**

**What is built (MVP-A):**

- **Data:** Deterministic synthetic OHLCV universe (`QPX.A` through `QPX.E`, five instruments, approximately two years of daily bars) generated by `app/quant/synthetic.py`. No real market data dependency for development or demo.
- **Feature set:** Six Polars rolling features — `mom_5`, `mom_20`, `vol_20`, `return_mean_20`, `hl_range`, `vol_ratio_20` — implemented as Polars transformation functions in the silver-to-gold layer.
- **Baseline model:** LightGBM with time-ordered train/validation split, early stopping, and MLflow `pyfunc` wrapper for serving parity.
- **Validation:** Walk-forward harness and PBO/DSR infrastructure present; CPCV scaffolded.
- **Output:** Daily ranked predictions and inference log, surfaced in the Models UI.

**Deferred to post-MVP-A:**

- CSI 300 (or equivalent real-data) ingestion via Qlib's `GetData` path.
- Alpha158 (158 hand-engineered expressions) and Alpha360 (raw OHLCV reshaped to 360-dimensional panel) implemented as Polars transformations — the bronze→silver→gold contract is compatible; the transformation functions are not yet written.
- LSTM baseline and Transformer models (iTransformer, MASTER, or equivalent).
- US-equity variant using Sharadar-free or Yahoo Finance.

The Qlib-style workflow is the right framing for five reasons that remain valid at MVP-A scope:

1. **Zero IP risk.** Qlib is MIT-licensed; synthetic data has no licensing constraints; the model architectures are academic.
2. **Audience-recognisable pattern.** The cross-sectional ranking workflow (features → GBDT → IC-based evaluation → promotion gate) is the vocabulary of systematic equity quants regardless of the specific data source.
3. **Covers every layer.** The MVP-A workload exercises data ingestion, silver/gold transformation, point-in-time discipline, feature engineering, training, walk-forward validation, model registry, serving, and audit trail. No layer of the platform is a mock.
4. **Upgrade path is clear.** Swapping synthetic data for real CSI 300 bars is a single function change in the bronze loader; the silver/gold contract, training worker, and serving path are unchanged.
5. **Extensible.** Alpha158/Alpha360 feature sets, additional asset classes, and advanced model architectures are additive post-MVP-A work, not rearchitecting work.

A viewer of the MVP-A demo sees the Qlib-style workflow shape clearly. The gap relative to the original PRD spec — real CSI 300 data, the full 158-expression Alpha158 feature set, advanced Transformer models — is real and is not papered over. Those items are the first priority in the post-MVP-A sprint.

### 3.3 User journey — the 30-minute demo

The demo's narrative spine, beat by beat. Each beat has a corresponding UI screen (§4.3) and a corresponding platform capability (§4.1-§4.2).

**Beat 1: Opening (0:00-2:00) — the platform overview.** The demo opens on the platform's home dashboard scoped to a single tenant. The viewer sees a small set of KPIs (active strategies, models in production, daily inference count, open audit items), a recent-activity feed, and a left navigation listing the major areas (Data, Research, Models, Deployments, Audit). The dashboard is *information-dense in the Bloomberg sense*, not sparse.

**Beat 2: Data provenance (2:00-7:00) — where the data comes from, and how we know.** Navigation to the Data area. The viewer sees the list of inbound data sources (CSI 300 bar data via scheduled pull, Alpha158 derived features, Alpha360 raw reshape). Clicking a source opens a timeline of files received, with content hashes, sizes, schemas, and validation results. Clicking a single bronze file shows its silver derivations and the gold aggregates that depend on it. Clicking a silver row shows its `_knowable_at`, `_valid_from`, `_valid_to` columns and a link to the exact bronze file that produced it. The bi-temporal story is told by the UI, not narrated over it.

**Beat 3: Research workspace (7:00-12:00) — how a quant would propose a new signal.** Navigation to the Research area. The viewer sees an existing strategy family (CSI-300-momentum-family) with several prior experiments. The demo creates a new experiment by editing a Polars feature function in the platform's integrated notebook view (Marimo- or Jupyter-Lab-embedded), running it against the gold layer, and submitting it as a training run. The training run appears in MLflow, tracked by the platform's registry wrapper. The demo highlights two things: (a) the feature function is *code* that lives in the git repo, not a notebook cell that will rot; (b) the training run launches on the platform's Cloud Run Job infrastructure with a single click.

**Beat 4: Backtest and validation (12:00-18:00) — the credibility gate.** The training run completes; the demo navigates to its result. The viewer sees a walk-forward evaluation (sequence of train windows, each with its out-of-sample period), a backtest equity curve with realistic transaction-cost assumptions, and the PBO and DSR statistics prominently displayed alongside the headline Sharpe. The UI shows a second, identical panel for the comparison models (baseline LightGBM, baseline LSTM, the Transformer). The demo highlights that PBO > 0.7 (high probability of backtest overfitting) or DSR < 1.0 would block promotion; the current model passes both. As a visual aside, the demo opens the embedded Dagster UI (`/dagster/*`) showing the strategy's walk-forward asset graph with per-fold materialization status — the same evidence rendered as a visual DAG, useful for the operator and legible to a sophisticated viewer who recognises Dagster.

**Beat 5: Model promotion (18:00-22:00) — the governance beat.** The demo navigates to the Models area. The new model version is selected; its registry entry shows the training dataset fingerprint, the validation report, the `pyfunc` artefact hash, the authoring commit SHA. The demo promotes the model using the UI's promotion flow, which requires a reason, records an event in the audit log with cryptographic chaining, and triggers the serving reload. The promotion appears on the home dashboard's activity feed within seconds.

**Beat 6: Serving and audit (22:00-26:00) — the LP-visible moment.** The demo navigates to the Serving area. The viewer sees the production model's recent inference log — every request logged with timestamp, feature-vector hash, output, latency. The demo selects a single historical inference from 14 days ago and shows its full lineage: the request, the model version that served it, the training dataset it was trained on, the bronze source files that produced that training dataset. This single drill-down answers Priya's (§2.2) most frequent ODD question in 15 seconds. The same lineage is also drillable into the Dagster asset graph: the inference asset's upstream ancestry resolves to the same bronze sources, with materialization timestamps and asset-check results visible inline.

**Beat 7: LP-facing report (26:00-30:00) — the closing beat.** The demo navigates to the Reports area and generates the LP quarterly-report view for the strategy. The viewer sees: factor-decomposed return attribution, drawdown statistics, model version history, key audit-trail statistics (promotions, demotions, unusual events), and an exportable PDF that could go straight into an LP letter. The demo closes on the question "how many managers could show you this view, today, without manual work?" — and answers it implicitly.

The total narrative is 30 minutes, structured as seven beats of 4-6 minutes each, with natural pause points for questions. The beats work in sequence as a single narrative and individually as standalone demos scoped to specific questions.

### 3.4 User stories

Organised by persona, with acceptance criteria.

**Morgan (primary — HF quant/eng lead):**

- *US-1.1 (feature velocity).* As Morgan, I want to add a new feature function to the feature library, submit a training run, and see walk-forward results, all without writing any pipeline code, so that my quants can test ideas in hours rather than weeks. **Acceptance:** From a blank git branch, a Morgan-persona user completes feature-to-walk-forward-result in under 15 minutes of wall-clock time, with no engineering support requested.

- *US-1.2 (model promotion governance).* As Morgan, I want every model promotion to be recorded in an immutable audit trail with a required reason field, so that our next ODD cycle does not repeat last year's findings. **Acceptance:** The audit log is append-only (verified by attempting a SQL UPDATE and observing the constraint); every promotion requires a reason field; the audit trail is exportable in a format an auditor accepts.

- *US-1.3 (research-to-production parity).* As Morgan, I want the Python function that computes a feature in a research notebook to be the same function that computes it in production inference, so that train-serve skew ceases to be a class of bug on my team. **Acceptance:** A demo modification to a feature function, committed and promoted, changes both backtest behaviour and production inference behaviour on the next model version.

- *US-1.4 (walk-forward enforcement).* As Morgan, I want walk-forward validation to be *enforced* by the platform — a model with insufficient walk-forward evidence cannot be promoted — so that I do not have to police this by review. **Acceptance:** A model with PBO > 0.7 or with fewer than K walk-forward folds configured blocks the promotion UI with a visible explanation.

- *US-1.5 (LLM-assisted signal discovery, stretch for v1).* As Morgan, I want to invoke an LLM-assisted signal-mining workflow that proposes new feature functions, implements them in code, and submits them through the normal backtest harness, so that my team can explore a larger hypothesis space per unit of quant time. **Acceptance:** The LLM mining workflow produces at least one committable feature function and runs the full backtest pipeline on it without engineering intervention. Marked stretch because the full AlphaGPT pattern is Phase-2; v1 includes the scaffolding for it but not the full agentic loop.

**Priya (secondary — LP allocator running ODD):**

- *US-2.1 (specific inference drill-down).* As Priya, I want to ask a manager "show me a specific inference from 18 months ago and its full lineage," and receive a demonstrable answer in under 60 seconds. **Acceptance:** The demo's Beat 6 is reproducible on demand for arbitrary historical inferences within the retention window.

- *US-2.2 (data-discipline evidence).* As Priya, I want to see evidence that the manager's training pipeline filters on a system-knowable-at-the-time timestamp, so that look-ahead bias is not a verbal claim but a UI fact. **Acceptance:** The Data area's file-detail view shows `_knowable_at`, `_valid_from`, `_valid_to` columns on silver rows, and the Research area's training-run view shows the `as_of` filter applied.

- *US-2.3 (walk-forward evidence).* As Priya, I want to see the walk-forward methodology *as applied*, including the PBO and DSR of the production models, without the manager having to explain the methodology to me. **Acceptance:** The Models area's version-detail view displays PBO and DSR as first-class fields with tooltips linking to López de Prado's definitions.

**Platform operator (tertiary):**

- *US-3.1 (one-command demo).* As the operator running a demo at a client office, I want a single command that spins up a fresh tenant with seeded Qlib data and pre-loaded demo state, so that I can arrive at a meeting with no pre-work required. **Acceptance:** `make demo-fresh` produces a fully seeded demo in under 5 minutes on a MacBook.

- *US-3.2 (repeatable narrative).* As the operator, I want the seven-beat demo narrative to be repeatable from a clean state, so that I can practice it and so that NotebookLM-generated videos of it are consistent. **Acceptance:** The demo-scripts directory contains seven numbered scripts, each of which advances the demo by one beat, and each of which is idempotent.

- *US-3.3 (easy UI iteration).* As the operator, I want to iterate on a UI screen's layout without rebuilding the backend, so that the demo's visual storytelling can be refined without engineering overhead. **Acceptance:** Vite dev-server hot-reload works against the running demo stack; component changes propagate in sub-second.

### 3.5 Success metrics

Not all success metrics are measurable at v1 launch. They are stated here for the Phase-2/3 horizon with leading indicators measurable at v1.

**Commercial leading indicators (v1 launch):**

- Demo conversion rate: of prospects shown the 30-minute demo, what fraction advance to a paid pilot conversation? **Target: 40%** (baseline: unmeasured, likely < 15% on the current platform).
- Time-to-pilot: from first demo to signed pilot. **Target: 30 days** for the first three pilots; **Target: 14 days** at steady state.
- Demo qualitative feedback: structured post-demo survey with Likert scales on "looks credible," "answers my data-discipline questions," "I can see my team using this." **Target: 4.0/5.0 on each** across the first ten demos.

**Technical leading indicators (v1 launch):**

- Demo reproducibility: can the 30-minute narrative be replayed from a clean state without manual intervention? **Target: 100% pass rate** on `make demo-fresh && pytest demo/e2e.py`.
- Fresh-clone time: from blank MacBook to first successful `make demo-fresh`. **Target: under 30 minutes** including dependency install.
- Feature-to-walk-forward-result time: from blank git branch to a full walk-forward evaluation result. **Target: under 15 minutes** per US-1.1.

**Product quality (v1+3 months):**

- UI performance: p95 page load for any screen under 2 seconds on a realistic client machine. **Target: 95% of pages meet.**
- Demo bug rate: bugs discovered during demos that require verbal narration to work around. **Target: zero** in a 30-minute walkthrough.

**Business outcome (v1+6 months):**

- Paying pilots: number of hedge-fund customers on a paid pilot. **Target: 3.**
- Reference customer count: customers willing to have their usage described to prospects. **Target: 1.**

These targets are stretched; their purpose is to make "good" measurable.

---

## 4. Requirements

### 4.1 Functional requirements

Organised by the seven demo beats; each functional requirement is marked MUST / SHOULD / MAY per prioritisation.

**Beat 1 — platform overview (home dashboard):**

- MUST: Tenant-scoped home dashboard with an at-a-glance strategy/model/inference count and a recent-activity feed.
- MUST: Left-side primary navigation to Data / Research / Models / Deployments / Audit.
- SHOULD: Customisable KPI tiles (operator or customer can choose which KPIs to surface).
- MAY: Per-user "pinned" items to the dashboard.

**Beat 2 — data provenance (Data area):**

- MUST: Data-source inventory listing all configured inbound sources with cadence, last-received time, and validation status.
- MUST: File-detail drill-down showing per-file content hash, schema, validation result, lineage to silver derivations.
- MUST: Silver-row detail showing `_knowable_at`, `_valid_from`, `_valid_to` columns and a click-through to the bronze file that produced it.
- MUST: Gold-aggregate detail showing the silver sources feeding it and any re-computation lineage.
- SHOULD: Visual timeline of restatement events (bronze file received, silver re-derived, gold re-aggregated).
- MAY: Natural-language query of the lineage graph ("show me every gold row that depends on this bronze file").

**Beat 3 — research workspace (Research area):**

- MUST: Experiment-family view showing a strategy family and its prior experiments with a performance leaderboard.
- MUST: Integrated code-first feature-authoring environment — not a full notebook, but a Polars-function editor with schema validation and quick-preview against gold data. Marimo preferred; Jupyter-Lab fallback.
- MUST: Single-click training-run submission that dispatches to Cloud Run Jobs and tracks in MLflow.
- MUST: Reproducibility metadata recorded with every training run (code commit SHA, data snapshot fingerprint, hyperparameter set, environment hash).
- MUST: Dagster asset graph view at `/dagster/*` showing the strategy's full pipeline DAG (bronze → silver → gold → features → training_run → model_version → inference) with per-asset materialization status, asset-check results, and run history. Read-only by default; quant-role users can trigger materialization.
- SHOULD: Hyperparameter search via Optuna from the UI.
- SHOULD: Run comparison view showing metrics side-by-side across runs.
- MAY (stretch US-1.5): LLM-assisted signal mining — a separate workflow where the user describes a hypothesis and the system proposes a feature function implementation, implements it, and runs a training-backtest cycle.

**Beat 4 — backtest and validation:**

- MUST: Walk-forward evaluation with configurable step and holdout, rendered as a sequence of OOS performance points.
- MUST: Backtest equity-curve panel with realistic transaction costs (Almgren-Chriss-style simple model is adequate for v1).
- MUST: Probability of Backtest Overfitting (PBO) computed automatically on every backtest and displayed prominently.
- MUST: Deflated Sharpe Ratio (DSR) computed and displayed alongside headline Sharpe.
- MUST: Combinatorial Purged Cross-Validation (CPCV) as the CV method; configuration visible in the run metadata.
- MUST: Comparison-to-baseline panel (baseline GBDT and baseline LSTM always run; user can add their model).
- SHOULD: Drawdown analysis with time-in-drawdown, max-drawdown, recovery time.
- SHOULD: Factor-decomposed return attribution against Fama-French or Hou-Mo-Xue-Zhang factors.
- MAY: Intraday / minute-bar extension for futures or FX demos (v1 is daily-bar only).

**Beat 5 — model promotion (Models area):**

- MUST: Model-registry view with version history, lifecycle state (staging, production, archived), authoring commit, training dataset fingerprint.
- MUST: Promotion flow that requires a reason field, records a `ModelPromoted` event to the immutable audit log, and triggers serving reload.
- MUST: MLflow Model Aliases (not deprecated Stages) as the lifecycle mechanism.
- MUST: Gate enforcement — promotion blocked if PBO > threshold or if walk-forward fold count < threshold.
- SHOULD: Automated model-card generation summarising the model's training data, intended use, known limitations.
- SHOULD: Champion-challenger view allowing side-by-side comparison of a production model with a candidate.
- MAY: A/B traffic split between model versions (Phase 2; scaffolded but not exercised in v1).

**Beat 6 — serving and audit:**

- MUST: Live inference log with filterable view by model, time range, user, error status.
- MUST: Per-inference drill-down showing request, output, feature-vector hash, latency, model version.
- MUST: Lineage drill-down from inference → model version → training dataset → bronze source files (the "Priya's 60-second answer" capability).
- MUST: Cryptographically chained audit trail (each row includes hash of prior row) for security/compliance events.
- SHOULD: Exportable audit log in WORM GCS with Object Lifecycle Lock for regulated customers.
- SHOULD: Inference replay — re-run a historical inference against the current model version and compare outputs.
- MAY: Distributional inference outputs (quantile responses) for options-heavy or risk-focused workflows. Scaffolded in v1 but not exercised unless the demo requires it.

**Beat 7 — LP-facing report (Reports area):**

- MUST: Quarterly-report-style view for a strategy with factor decomposition, drawdown, model history, audit summary.
- MUST: PDF export of the report, formatted for inclusion in an LP letter or ODD response.
- SHOULD: Per-report customisation (select date range, select factor model, toggle sections).
- SHOULD: Comparison-to-benchmark panel (strategy vs the S&P 500 or a quant benchmark).
- MAY: Customer-facing IAM-limited read-only access so LPs can view their own manager's reports directly (Phase 2).

### 4.2 Technical requirements

Derived from the research synthesis's Part 6 (platform map) and the seven gaps. Marked by which research gap they address.

**Gap 1 (backtest as a first-class service):**

- T1.1: A `worker-backtest` role, stamped from the same image, running backtest jobs enqueued via PGMQ.
- T1.2: A backtest-job API endpoint accepting (model_id, dataset_snapshot_id, walk_forward_config, transaction_cost_model_id).
- T1.3: A structured backtest-result aggregate in the domain model, queryable via the Models area.
- T1.4: Polars-based backtest engine (vectorbt as reference but re-expressed on Polars for performance); initial engine supports equity universes with daily data.

**Gap 2 (PBO/DSR as platform defaults):**

- T2.1: Library implementation of López de Prado's PBO (combinatorially symmetric cross-validation variant) and DSR.
- T2.2: Automatic computation on every backtest result, stored in the backtest aggregate.
- T2.3: Thresholds configurable per tenant; defaults chosen from the literature (PBO > 0.5 warning, > 0.7 block; DSR < 1.0 block).
- T2.4: UI exposure in the Models area with tooltips linking to original methodology papers.

**Gap 3 (walk-forward enforcement):**

- T3.1: Walk-forward is not a library option but a platform-level configuration on the model-family level.
- T3.2: A model whose latest training did not produce the configured minimum number of walk-forward folds (default: 5 folds; tenant-configurable) cannot be promoted; the Models area's promotion UI surfaces the gate visibly.
- T3.3: The walk-forward config (step size, holdout size, minimum folds) is versioned with the model family; changing it invalidates prior walk-forward evidence.

**Gap 4 (research-to-production parity):**

- T4.1: Every feature is a Python function in the `features/` module, callable from both training and serving paths.
- T4.2: MLflow `pyfunc` wrappers package the inference wrapper with the trained model artefact; the same `predict()` call works in the research notebook and in the production inference endpoint.
- T4.3: Contract tests validate that the same inputs produce the same outputs in both contexts; CI fails on skew.
- T4.4: The Research area's notebook environment imports the `features/` module directly, not a copy.

**Gap 5 (immutable audit trail):**

- T5.1: A Postgres `audit_log` table with an `event_hash` column that is the SHA-256 of (prior_row_hash || this_row_contents); a trigger enforces correctness on insert.
- T5.2: Updates and deletes are disallowed by a RULE rewriting them to raise an exception.
- T5.3: Nightly export to a WORM GCS bucket with Object Lifecycle Lock for regulated tenants.
- T5.4: An `audit-verify` CLI and admin-UI action that verifies the hash chain from genesis to present.

**Gap 6 (LLM signal-mining scaffolding, partial — stretch):**

- T6.1 (v1 stretch): A `worker-llm-research` role running a local Llama-class model or calling out to Anthropic API, with prompts structured for formulaic-alpha discovery.
- T6.2: A closed-loop interface where the LLM proposes a feature function, implements it in code, submits a training + backtest job, and receives the result back for the next iteration.
- T6.3: Strict sandboxing; the LLM cannot write to production code, only to a research branch that requires human review before any CI merge.
- T6.4: Explicit disclosure in the UI that a feature or model was LLM-authored, with the prompt history attached.

**Gap 7 (Dagster orchestration as software-defined-asset substrate):**

Dagster is added to v1 as the asset-materialization, lineage, and visual-DAG layer. It coexists with the existing PGMQ + APScheduler stack rather than replacing either: PGMQ remains the CQRS command/event flow, APScheduler remains the in-process cron (which now triggers Dagster runs rather than calling pipeline functions directly), and Dagster owns software-defined-asset materialization, lineage capture, asset checks, and the visual DAG surface. The decision is locked (see §5); the choice over Prefect / Airflow / Temporal is not an open question.

- T7.1: Dagster webserver and Dagster daemon run as docker-compose services locally and as Cloud Run services in production, stamped from the same image with `webserver` / `daemon` role flags. The webserver is fronted by the BFF; the daemon owns sensor and schedule execution.
- T7.2: An `app/dagster_defs/` module exports a `Definitions` object containing software-defined assets for the bronze / silver / gold layers — bronze and silver as static assets per data source, gold as static assets per derived feature set. Pipeline functions are wrapped (not rewritten) as `@asset` decorators; the Polars functions remain the source of truth.
- T7.3: Dynamic asset generation per registered strategy: `training_run` and `model_version` are dynamic assets parameterised by strategy id, generated at Definitions-load time from the strategy registry. The SDK's `register()` call writes a Dagster asset definition file into a watched directory; the daemon picks it up on the next reconciliation tick.
- T7.4: Asset checks for data-quality validation, backed by Pandera schemas. Each silver and gold asset has at least one Pandera-backed asset check (schema conformance, null-rate bounds, value-range bounds); a failed check blocks downstream materialization and surfaces in both the Dagster UI and the platform's Audit area.
- T7.5: Dagster UI proxied via the BFF on `/dagster/*`. Read-only by default; trigger actions (manual materialization, backfill, sensor enable/disable) gated to the quant role. Authentication is the BFF's session cookie; the BFF rewrites the upstream Dagster URL and forwards the user's role for fine-grained authz.

**Non-gap technical requirements** (not from the research synthesis but v1-critical):

- T8.1: The UI must be a Vite-built React 19 SPA served either by the application container or by Cloud CDN (per blueprint).
- T8.2: The UI must use the same stack patterns as the user's Doodle-1 reference project: TanStack Router for client routing, TanStack Query for server state, shadcn/ui + Radix + Tailwind v4 for components, Geist fonts for typography (confirm via §8 open question).
- T8.3: The API is OpenAPI-generated and the client is generated from the OpenAPI spec via `openapi-typescript`; zero drift between server and client contracts.
- T8.4: Demo seed data (synthetic OHLCV universe `QPX.A`–`QPX.E`, Polars rolling features, at least one pre-trained LightGBM model with MLflow registry entry, 14 days of inference log, a populated audit log) must be reproducible via `make demo-fresh`. Real CSI 300 bars and Alpha158/360 features replace the synthetic data post-MVP-A.

### 4.3 Design requirements

This section is where the "strong visual impactful UI" mandate becomes concrete. UI direction will be iterated with the visual companion in the next phase; what the PRD locks in here is the principles, the screen inventory, and the fidelity target.

**Design principles (v1):**

- **Financial-professional register.** The visual language is dense, data-first, dark-mode-by-default-with-light-as-secondary, grid-aligned, monospace-for-numbers, and sparing with colour (colour reserved for semantic signal, not decoration). Inspiration: Bloomberg Terminal, TradingView Pro, Man AHL's internal tooling (where publicly glimpsed), Palantir Gotham's desktop views.
- **Information-dense over minimalist.** A quant reviewing model performance expects to see many numbers at once. Whitespace is a cost, not a virtue, at the primary workspace. Onboarding screens and empty-states can be lighter.
- **Keyboard-first for power users.** Every primary action has a keyboard shortcut displayed inline. Global command palette (Cmd-K) as the top-level navigation for experienced users.
- **No animation for animation's sake.** Transitions where they communicate state change (a row highlighting after a promotion); no decorative animation.
- **Visible discipline.** The UI visibly surfaces the platform's audit, lineage, and governance properties. These are features that sell; they must be seen to be sold.
- **Typography:** Geist (sans) for UI, Geist Mono for numerics and identifiers, per user's Doodle-1 reference.

**Screen inventory (v1):**

Bolded screens are **hero screens** — the ones whose visual polish is invested in, and the ones that anchor the NotebookLM video. Unbolded screens are first-class but can be at lower visual polish.

- Login and tenant selection (plain, brand only)
- **Home dashboard** (hero — Beat 1)
- Data area:
  - Data-source inventory
  - **File-detail view with lineage** (hero — Beat 2)
  - Silver-row detail view
  - Gold-aggregate detail view
- Research area:
  - Experiment-family leaderboard
  - **Feature-authoring environment** (hero — Beat 3)
  - Training-run submission
  - Training-run detail view
- Validation area:
  - **Backtest results view with PBO/DSR and walk-forward** (hero — Beat 4)
  - Run comparison view
- Models area:
  - Registry index
  - **Model-version detail with promotion flow** (hero — Beat 5)
  - Champion-challenger view
- Deployments / Serving area:
  - Live inference log
  - **Per-inference drill-down with full lineage** (hero — Beat 6)
  - Distributional-output view (stretch)
- Reports area:
  - **Quarterly report view** (hero — Beat 7)
  - PDF preview and export
- Audit area:
  - Audit-log browser
  - Audit verification view (the chain-verify UI)
- Admin area (operator-only):
  - Tenant settings
  - User and role management
  - Data-source configuration
  - Model-family configuration

**Seven hero screens total** — one per demo beat. This matches the fidelity recommendation from earlier in the brainstorming session (high fidelity on the hero triad → evolved to hero septet since each beat is load-bearing).

**Fidelity target:**

- Hero screens: React-implemented with real backend data, visual polish at a level where a stillframe could be shared as a standalone marketing image. Estimated 40-60 hours of design + frontend work per hero screen at first pass.
- Non-hero screens: React-implemented with real backend data, functional but not visually headlining. Estimated 10-20 hours of frontend work each at first pass.

**Design artefacts required before implementation:**

- Design-system snapshot: Tailwind v4 theme, typography scale, colour palette with semantic tokens (danger, warning, success, info, neutral in at least 4 shades each), spacing scale, radius and shadow tokens. One document.
- Screen mockups for the seven hero screens at 1440×900 viewport, exported as PNG and committed under `design/mocks/`.
- Component inventory: the shadcn/ui components we accept as-is, the ones we customise, and the custom components we add (likely: `TickerTable`, `EquityChart`, `DrawdownChart`, `LineageGraph`, `FactorAttribution`).

---

## 5. Out of Scope (v1)

Explicit non-goals. Each is a deliberate deferral.

**S-1. Intraday / tick-level data and serving.** The demo is daily-bar. Adding minute or tick data adds a storage-engine layer (TimescaleDB hypertables) and a microstructure-aware backtest engine that is Phase-3 work. The v1 demo narrative does not require it.

**S-2. Multi-asset beyond equities.** Fixed income, commodities, FX, crypto, options — all out of scope. The platform architecture supports them; the v1 demo is single-asset for narrative clarity.

**S-3. Full LLM signal-mining (AlphaGPT pattern).** The *scaffolding* for LLM signal mining is in v1 (T6.1-T6.4) but the closed-loop agentic workflow is Phase-2. V1 demo includes one pre-generated LLM feature to show the pattern is possible, but the workflow is operator-piloted, not autonomous.

**S-4. Customer-facing BYOC (Bring-Your-Own-Cloud).** The platform runs in the vendor's GCP project for v1. The Terraform modules are in place for BYOC; the customer-owned deployment path is a Phase-2 exercise.

**S-5. Real-time dashboards.** Home-dashboard KPIs refresh on navigation, not in real time. Real-time is a Phase-3 feature.

**S-6. Regulatory compliance certification (SOC 2 Type II, etc.).** The platform has the controls; the certification itself is a separate commercial exercise timed to the first compliance-demanding customer.

**S-7. Feature store (Feast).** The research synthesis noted a reconsider trigger; v1 ships without Feast. Re-evaluate when three or more strategies share meaningful feature code.

**S-8. Non-English UI.** Interface in English only for v1; localisation layer is deferred.

**S-9. Mobile UI.** The UI is desktop-optimised. Responsive breakpoints exist but mobile is not a first-class experience for v1.

**S-10. Alternative-data vendor integrations as concrete features.** The blueprint's four ingestion patterns (scheduled pull, push to GCS, push via SFTP, customer-operated drop) are the generic shapes. Specific vendor integrations (RavenPack, Orbital Insight, etc.) happen per-customer post-v1.

**S-11. Re-evaluating the orchestration choice.** Dagster is locked in as the asset-materialization, lineage, and visual-DAG layer for v1 (see §4.2 T7). The choice over Prefect, Airflow, and Temporal has been made deliberately and is not an open question for v1. Prefect was rejected on weaker lineage and asset-graph affordances; Airflow on the heaviness of its DAG-as-code register and its workflow-not-asset orientation; Temporal on the mismatch between its workflow-engine semantics and a data-asset materialization workload. Re-litigating the choice within v1 is out of scope; revisit only at Phase 3 if Dagster's operational profile fails (and see OQ-11 for the orthogonal Cloud-vs-self-hosted question).

---

## 6. Implementation Notes

### 6.1 Dependencies on the existing blueprint

V1 assumes the blueprint's foundational phases (Phase 0 — foundations, Phase 1 — minimum viable platform) are delivered. Specifically, v1 assumes:

- The docker-compose local stack (Postgres with extensions, MinIO, MLflow, mock OIDC) works.
- The single-image-multi-role pattern is implemented; adding `worker-backtest` and `worker-llm-research` is a configuration change, not an architectural one.
- The CQRS event log and PGMQ queueing are in place.
- The Terraform module for per-tenant provisioning exists.
- The CI/CD pipeline deploys to a staging Cloud Run instance.
- The audit_log table exists but may need the hash-chain trigger added (T5.1).

V1 does *not* depend on:

- The control plane (Phase 5). V1 demos run on an operator-managed tenant; the control plane is scaffolded but not exercised.
- Wave-based rollouts. V1 is a single-tenant demo.
- SOC 2 readiness (Phase 6).

### 6.2 Sequencing (what to build in what order)

The sequence is chosen for narrative readiness — the earliest viewable subset of the demo is the earliest valuable.

**Sprint 0 — design and scaffolding (2 weeks):**

- Design-system snapshot finalised (§4.3).
- Seven hero-screen mockups produced.
- `worker-backtest` role scaffolded (empty implementation).
- PRD review and sign-off.

**Sprint 1 — data and lineage (3 weeks):**

- Synthetic OHLCV universe (`QPX.A`–`QPX.E`) as the bronze source for MVP-A; Qlib CSI 300 ingestion deferred to post-MVP-A.
- Polars rolling features (`mom_5`, `mom_20`, `vol_20`, `return_mean_20`, `hl_range`, `vol_ratio_20`) implemented in the silver/gold layers. Alpha158 and Alpha360 transformations are post-MVP-A.
- Bi-temporal columns enforced on silver and gold rows (`_knowable_at` + `_valid_from` / `_valid_to`).
- Polars pipeline functions wrapped as Dagster `@asset` decorators in `app/dagster_defs/`; bronze and silver assets materialise via Dagster runs triggered by APScheduler cron entries (the pipeline functions remain the source of truth, the wrapping is thin).
- Pandera-backed asset checks attached to each silver and gold asset (T7.4).
- Data area UI: source inventory + file-detail + silver-row detail + gold-aggregate detail.
- Beat 2 of demo runnable end-to-end.

**Sprint 1.5 — Dagster foundation (1 week):**

- Dagster webserver and daemon services added to docker-compose; production Cloud Run service definitions drafted (T7.1).
- `app/dagster_defs/` module skeleton with a `Definitions` object exporting the bronze/silver/gold static assets defined in Sprint 1, plus the dynamic-asset factory for `training_run` / `model_version` keyed on strategy id (T7.2-T7.3).
- BFF proxy route `/dagster/*` with read-only enforcement and quant-role gate for trigger actions (T7.5).
- SDK `register()` updated to write a Dagster asset definition into the watched directory.
- Smoke test: a single end-to-end materialization (bronze → silver → gold) runs from the Dagster UI against the synthetic universe.

**Sprint 2 — research and training (3 weeks):**

- Feature-authoring environment (Marimo or Jupyter-Lab embed).
- MLflow tracking server and registry configured.
- Training-run submission and detail view.
- Baseline LightGBM implementation trained against synthetic rolling features. LSTM and Transformer models (Alpha158/Alpha360) deferred to post-MVP-A.
- Beat 3 of demo runnable end-to-end.

**Sprint 3 — validation (3 weeks):**

- Walk-forward harness as a configurable platform-level construct.
- PBO and DSR implementations, computed automatically on every backtest.
- CPCV as the cross-validation method.
- Backtest-results UI with equity curve, drawdown, factor attribution.
- Beats 4 of demo runnable end-to-end.

**Sprint 4 — governance and serving (3 weeks):**

- Model registry and promotion UI.
- Immutable audit log with hash chaining (T5.1-T5.4).
- Serving lazy-reload on `ModelPromoted` events.
- Inference log and drill-down with full lineage.
- Beats 5 and 6 of demo runnable end-to-end.

**Sprint 5 — LP report and hero polish (2 weeks):**

- Quarterly-report view with factor decomposition and PDF export.
- Visual polish pass on all seven hero screens.
- Dagster UI treated as an eighth hero surface for demo purposes — no visual rebuild (it's an existing UI we expose, not one we build), but the embed treatment (BFF iframe wrapper, theme reconciliation against the Tailwind v4 dark palette where possible, navigation breadcrumbs that bridge between platform and Dagster views) is polished so the surface reads as part of the product, not as a bolted-on third-party tool.
- Beat 7 of demo runnable end-to-end; all seven beats runnable as single narrative.

**Sprint 6 — LLM scaffolding stretch + demo hardening (2 weeks):**

- T6.1-T6.4 scaffolding for LLM signal mining (stretch).
- `make demo-fresh` command with full seeded state.
- Demo-scripts directory with one script per beat.
- NotebookLM-ready recording of the 30-minute narrative.
- End-to-end integration test that reproduces the demo from scratch.

**Total: 19 weeks, or ~4.75 months** from sprint 0 start to v1 launch — Sprint 1.5 adds one week to the original 18-week plan to absorb Dagster foundation work.

This sequence is agentic-implementation-friendly: each sprint has a discrete acceptance condition (a specific demo beat runs end-to-end), sprints are independently testable, and the sequence does not require a full-stack refactor late in the process.

### 6.3 Resources

- **Design.** Hero-screen mockups require a designer familiar with financial-professional UI. 60-80 hours of design for v1; if outsourced, budget $15-25k. If done in-session with a design-partner tool (v0, Dora, Figma Make), compressed to 30-40 hours + tooling cost.
- **Frontend engineering.** React 19 + TanStack + Tailwind v4 + shadcn/ui. Experienced frontend engineer working with the mockups can hit v1 in 12-14 weeks at 0.75 FTE.
- **Backend engineering.** Python + FastAPI + Polars + MLflow + Postgres. One full-time backend engineer (agentic-assisted) can plausibly deliver the backend in 12-14 weeks given the blueprint baseline.
- **Quant engineering.** MVP-A: synthetic universe, Polars rolling features, LightGBM baseline, PBO/DSR, CPCV, walk-forward harness. Post-MVP-A: Alpha158/360, LSTM baseline, one Transformer (iTransformer or MASTER). Strong quant-engineering hire needed; 8-10 weeks at 0.5 FTE for MVP-A scope.
- **Platform operator / ops.** Running demos, iterating the narrative, recording NotebookLM video. 0.25 FTE ongoing through v1.

Peak team size is approximately 3.5 FTEs during the central sprints. Early and late sprints are lighter.

---

## 7. Risks and Mitigations

**R-1 (severity: high; likelihood: medium) — UI fidelity budget overruns the sprint plan.** Financial-professional UI takes more design iteration than generic SaaS UI, and visual details (dense tables, number formatting, status pills) are where polish shows or doesn't. **Mitigation:** Commit the design-system snapshot in Sprint 0 before any screen implementation. Use shadcn/ui as the component baseline rather than building components from scratch. If the fidelity slips, drop non-hero screens to functional-only and preserve hero polish.

**R-2 (severity: medium; likelihood: low) — the synthetic demo workload feels unconvincing to a quant prospect.** A sophisticated viewer who recognises that `QPX.A`–`QPX.E` are synthetic tickers may discount the demo. **Mitigation:** The MVP-A narrative is honest that the data is synthetic for demo purposes; the productionalization infrastructure (audit trail, bi-temporal lineage, walk-forward enforcement, promotion gates) is real and is the demo's main value signal. Upgrading to real CSI 300 data is the first post-MVP-A milestone and is the correct response to a prospect who requires real-data evidence.

**R-3 (severity: medium; likelihood: high) — PBO/DSR implementation bugs.** López de Prado's methods have specific correctness conditions that are easy to get wrong. A bug that produces confident PBO numbers that are wrong is worse than no PBO at all. **Mitigation:** Implement against published reference cases with known PBO/DSR values; test with synthetic data where the true overfitting probability is known by construction; code review by someone who has read López de Prado's book.

**R-4 (severity: medium; likelihood: medium) — LLM signal-mining scope creep into v1.** T6.1-T6.4 are stretch; the temptation to make them non-stretch is strong because the AlphaGPT angle is commercially compelling. **Mitigation:** Hold stretch status unless the first five sprints complete ahead of schedule. If stretch stays stretch, the demo includes *one* hand-written feature presented as "an example of the kind of function the LLM pattern would produce" — honest and adequate.

**R-5 (severity: low; likelihood: n/a at MVP-A) — CSI 300 data licensing or data quality issues.** *(Deferred to post-MVP-A.)* MVP-A uses a synthetic universe, so this risk does not apply. When real data ingestion is added, CSI 300 is China A-shares and some customers may have a preference against Chinese data in a demo. **Post-MVP-A mitigation:** Implement CSI 300 first (Qlib's implementation is there), then add a US-equity variant using Sharadar-free or Yahoo; switch at the `make demo-fresh` parameter level.

**R-6 (severity: medium; likelihood: low) — audit-trail cryptographic-chaining bug that doesn't surface until a real audit.** A chain-integrity bug that escapes testing could invalidate a customer's audit posture; the customer wouldn't notice until their next ODD. **Mitigation:** `audit-verify` CLI runs as part of every CI build; Postgres trigger enforces correctness at insertion time; hash-chain invariant is a tested property.

**R-7 (severity: high; likelihood: low) — a security bug in the demo exposure path.** A public demo with a misconfigured service could expose internals or allow data exfiltration. **Mitigation:** Demo tenants run in the vendor's project only; demo URLs are non-indexed; IAM is locked to explicitly invited users; each demo run uses a fresh seeded tenant that is torn down afterwards.

**R-8 (severity: low; likelihood: high) — the operator's own narrative muscle memory weakens between demos.** A demo's 30-minute narrative requires practice; the operator running a demo after three weeks away from it will stumble. **Mitigation:** The demo-scripts directory is the source of truth for the narrative; each operator run starts from a scripted walkthrough. NotebookLM-generated video serves as the canonical "how the demo goes" reference for new operators.

**R-9 (severity: high; likelihood: medium) — the timeline estimate is optimistic.** 18 weeks with a 3.5-FTE peak is an ambitious target for this scope. **Mitigation:** Define a narrower "minimum demoable" subset (Beats 1, 2, 4, 5, 6 only — skipping Research environment polish and LP report polish) as a fallback. This subset is achievable in 12-14 weeks and preserves the audit/lineage/governance demo beats.

**R-10 (severity: medium; likelihood: low) — Jenny Lin's platform (peer/competitor) launches ahead of v1.** The same memory that suggests Jenny is a peer also suggests she is a peer *competitor* in the same market. **Mitigation:** Positioning is not identical (check the specifics in her actual launch when available); a differentiated demo focused on the audit-first angle, LLM-scaffold angle, or open-source-first angle is still valuable even if Jenny's product ships first. This is not a PRD issue; it's a market-positioning issue beyond the PRD's scope.

**R-11 (severity: medium; likelihood: medium) — Dagster operational complexity exceeds team capacity.** Adding a webserver + daemon pair, a Definitions-load lifecycle, sensor and schedule reconciliation, and a Cloud Run production posture is non-trivial for a team that does not have a Dagster operator on it. Misconfigurations (sensor loops, asset-key collisions, partition mismatches, run-storage Postgres pressure) can be opaque to debug and disruptive to demo. **Mitigation:** Lean on Dagster Cloud as a hosted-fallback path (see OQ-11); the Dagster team has substantially improved the local-dev story across 2025 and 2026, which lowers the day-one bar. Keep the Sprint 1.5 scope tight — only the asset surface needed for Beats 2 and 4, no advanced sensor or backfill machinery in v1. If operational pain materialises in Sprint 3 or Sprint 4, switch the production deployment to Dagster Cloud while keeping the local-dev compose path unchanged.

---

## 8. Open Questions

Decisions needed before or during build, collected here so they are not implicit.

**OQ-1 — UI stack exactness.** The Doodle-1 reference memory notes React 19 / Vite / TanStack Router / Tailwind v4 / Radix / Motion / Zustand / Sonner / Geist. Do we commit to that exact stack, or does v1 relax some of these (e.g., Motion, Zustand if Redux-lite alternatives in TanStack Query suffice)? **Default: adopt the stack verbatim unless an engineering reason surfaces.**

**OQ-2 — demo data: CSI 300 or US equities as default?** *(Post-MVP-A.)* MVP-A uses a synthetic universe. Once real data ingestion is added post-MVP-A, CSI 300 matches Qlib's published benchmark; US equities feels more natural to most customers. **Post-MVP-A default: CSI 300 for benchmark credibility; US variant available; operator picks per demo.**

**OQ-3 — embedded notebook: Marimo or Jupyter-Lab?** Marimo is newer, Python-reactive, cleaner for the non-notebook-fluent viewer. Jupyter-Lab is standard but less polished. **Default: Marimo; fall back to Jupyter-Lab if Marimo embedding proves hard.**

**OQ-4 — LLM for T6 stretch: local Llama-class or Anthropic API?** Local model runs on the Windows dev host's GTX 960 with 4GB — adequate for small Llama variants but limited. Anthropic API is higher-quality but is a billed external dependency. **Default: Anthropic API for the demo (quality matters more than cost for a demo); document both paths.**

**OQ-5 — design resourcing.** Design is the likely schedule-critical path. Do we retain an outside designer, use a v0-style AI design tool, or have the operator produce the mockups? **Default: operator produces first-pass mockups using v0 or Dora; design partner does polish pass in Sprint 5.**

**OQ-6 — pricing narrative.** Not a PRD question but informs positioning. Are we anchoring at $200-400k/year or $50-100k? This affects which customers the demo is built to convince. **Default: assume $200-400k for the v1 demo audience (mid-sized quant shops like Morgan).**

**OQ-7 — BYOC demo variant.** Do we have a customer asking for BYOC at v1 launch (requiring a second demo tenant in a customer-owned project)? **Default: assume no; BYOC remains scaffolded but undemonstrated until a customer requests.**

**OQ-8 — the seventh hero screen choice.** The screen inventory lists seven hero screens; if fidelity budget bites, which drops first? Recommend **Research area's feature-authoring environment** is the most-at-risk because polish on a code editor pays back less than polish on a chart or a report. **Default: drop Research polish before any of the six others.**

**OQ-9 — factor decomposition model in Beat 4 and Beat 7.** Fama-French three-factor, Carhart four-factor, or Hou-Mo-Xue-Zhang q-factor? The q-factor is more academically current; Fama-French is more broadly recognised. **Default: Carhart four-factor as a middle ground; offer q-factor as an alternative toggle.**

**OQ-10 — NotebookLM narrative cut.** The demo's 30-minute narrative is the source for the NotebookLM video but not necessarily identical to it. Is the NotebookLM video a direct capture of the demo, a synthesised narrative based on the demo + research synthesis, or a separate scripted piece? **Default: separate scripted piece drawing on both artefacts, with the demo's video capture used as B-roll where appropriate. Resolved in the NotebookLM-directive phase of the brainstorming.**

**OQ-11 — Dagster Cloud or self-hosted?** Dagster Cloud is the managed offering (Elementl-hosted control plane with customer-hosted compute via the Hybrid model, or fully managed via Serverless). Self-hosted means we run webserver + daemon on Cloud Run with a Postgres run-store. Self-hosted is preferred for tenancy (silo isolation per the platform's core posture), cost (no per-seat or per-credit Dagster Cloud billing in addition to GCP), and BYOC compatibility (a customer running BYOC cannot reasonably be asked to also pay Dagster Inc.). Dagster Cloud is preferred if operational burden becomes the gating cost (see R-11). **Default: self-hosted for v1 across both vendor and BYOC deployments; revisit at Phase 2 if the Sprint 1.5 + Sprint 3 + Sprint 4 operational experience suggests the burden outweighs the saving. The decision is reversible — Dagster Cloud's Hybrid model allows promoting the same Definitions module from self-hosted to managed without code change.**

---

## 9. Appendix

### A.1 Source materials

- `blueprint/src/01-executive-summary.md` through `blueprint/src/15-roadmap.md` — the platform architecture blueprint as currently written.
- `blueprint/research/2026-04-21-modern-quant-synthesis.md` — the quant research synthesis produced earlier in this brainstorming session.
- The `pmprompt/claude-plugin-product-management` PRD Writer skill template at `https://github.com/pmprompt/claude-plugin-product-management/blob/main/skills/prd-writer/SKILL.md` — the structural template this PRD follows.
- `blueprint/REVIEW_FINDINGS.md` — the pre-release review of the blueprint (all 24 findings addressed in this session).
- Dagster documentation at `https://docs.dagster.io/` — software-defined assets, Definitions module, asset checks, sensors and schedules, and the webserver/daemon deployment topology. Authoritative reference for the T7 series in §4.2.

### A.2 Memory references

- *Dev/staging deployment target*: Windows Docker host at 192.168.2.250 (`ssh windows`); self-hosted GH Actions runner for deploy jobs.
- *Dev GPU capability*: NVIDIA GTX 960 4GB on Windows dev host; CUDA 12.6.
- *Quant platform demo: Qlib-style workload*: Cross-sectional alpha workflow in the Qlib style. MVP-A uses a synthetic universe and Polars rolling features; real CSI 300 data and Alpha158/Alpha360 features are post-MVP-A.
- *UX patterns reference: Doodle-1*: copy frontend stack and component conventions from `/Users/igormusic/code/doodle-1`.

### A.3 Framework references

Frameworks applied (drawing on the pmprompt plugin's "26+ frameworks" mention, though applied loosely):

- **MoSCoW prioritisation** (MUST / SHOULD / MAY) — applied in §4.1.
- **JTBD (Jobs to be Done)** — implicit in persona construction (§2.1-§2.3).
- **User story format** — applied in §3.4.
- **SMART metrics** — applied in §3.5 (specific, measurable, with targets).
- **Risk matrix** (severity × likelihood) — applied in §7.
- **RACI** (responsible / accountable / consulted / informed) — not formally applied; consider for the sprint plan execution phase.
- **Kano model** — not formally applied but informs the hero-screen vs non-hero distinction (§4.3).
- **OKRs** — not formally applied at PRD level; success metrics in §3.5 are a simpler substitute.

### A.4 Glossary (v1-specific terms)

- **Hero screen** — a UI screen receiving first-pass design polish worth a standalone marketing stillframe; there are seven in v1.
- **The seven demo beats** — the seven narrative sections of the 30-minute demo, each anchored on a hero screen.
- **Qlib-style demo workload** — the MVP-A demo workload; a cross-sectional equity alpha workflow (synthetic universe + Polars rolling features + LightGBM) whose shape mirrors Microsoft Qlib's workflow. Real CSI 300 data and the full Alpha158/Alpha360 feature sets are post-MVP-A.
- **v1 / v1-demoable / demoable v1** — synonymous in this document; refers to the deliverable of this PRD.

### A.5 What this PRD does *not* cover

- Go-to-market plan (marketing, sales motion, pricing — out of scope).
- Hiring plan (resource numbers are indicative, not a recruiting brief).
- Legal and contracts (customer MSA, vendor agreements — out of scope).
- Specific customer commitments or names beyond Morgan and Priya as personas.
- Detailed design of any single UI component below the screen-level (that is the frontend-design skill's work in the next phase).

---

*End of PRD.*
