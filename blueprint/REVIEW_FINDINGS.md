# Blueprint Review Findings

## Summary

Twenty-four findings total: 5 in Check 1 (unfounded claims), 4 in Check 2 (missing source attributions), 7 in Check 3 (internal consistency — several load-bearing), 4 in Check 4 (logical consistency), 4 in Check 5 (hedging and over-confidence). The blueprint is well-organised and the architectural posture is consistent at the macro level, but there are two load-bearing internal contradictions that an external reader will notice immediately — the projector deployment shape (in-process asyncio tasks vs separate Cloud Run worker services) and the bi-temporal column naming (`_knowable_at` vs `_valid_from`/`_valid_to`). Several quantitative claims (Polars "5–30×", uv "10–100×", PGMQ "tens of thousands of messages per second", "the single most common cause of backtest failure") need either citations or softer wording before going to a sophisticated quant audience.

**Verdict:** Ready to share after addressing the seven load-bearing findings (3.1, 3.2, 3.3, 1.4, 1.1, 4.1, 1.3).

## Check 1: Unfounded claims

### Finding 1.1
- **File**: `src/01-executive-summary.md`, line 11
- **Quote**: "quant strategies are the favoured hedge-fund allocation heading into 2026, separately managed accounts — which require deploying dedicated instances per mandate — are now used by roughly a quarter of institutional investors"
- **Issue**: Two empirical assertions about the institutional-investor market are made with no citation. A Morgan Stanley reader will want a named source (BNP Paribas Capital Introduction, Barclays Strategic Consulting, Goldman Sachs Prime Services, or With Intelligence allocator surveys are the obvious candidates). "Roughly a quarter" is precise enough to look like a number from a survey but no survey is named.
- **Load-bearing**: Yes. The whole market-framing for the document rests on this paragraph; if it does not survive reader scrutiny the architectural justification (silo, BYOC, control plane) reads as solution-in-search-of-a-problem.
- **Proposed action**: Add inline attributions, e.g. "(BNP Paribas 2025 Capital Introduction Survey)" and "(With Intelligence SMA Industry Report 2025)", or soften to "industry surveys consistently report SMAs in roughly the 20–30% range of institutional allocators." If no specific source is at hand, soften: "are increasingly used by institutional investors."

### Finding 1.2
- **File**: `src/03-design-brief.md`, line 13
- **Quote**: "Separately managed accounts ... are now offered by roughly half of hedge funds and used by approximately a quarter of investors"
- **Issue**: Two specific quantitative claims, no citation. Same problem as Finding 1.1; this version adds the "half of hedge funds" figure that did not appear in the executive summary.
- **Load-bearing**: Yes (market framing).
- **Proposed action**: Cite the specific survey (With Intelligence "Hedge Fund SMA Report" or BNP Paribas Capital Introduction 2024/2025 results are the typical sources) or soften to "a substantial and growing share of hedge funds offer SMAs, and a meaningful minority of institutional investors use them."

### Finding 1.3
- **File**: `src/03-design-brief.md`, line 13
- **Quote**: "A published case study describes a hedge fund reducing its model-to-production workflow from 'weeks and a manual process' to 'a single configuration file and minutes,' achieved through an internal developer platform exposing golden paths for quants."
- **Issue**: Direct quotation marks imply an identifiable source, but no source is named. The reader cannot assess whether this is a Man Group, AQR, Two Sigma, BlackRock, or Bridgewater case study, or a vendor marketing piece. Quoting unnamed sources weakens credibility precisely where the document is trying to establish it.
- **Load-bearing**: Partially — it is used to validate the "golden path" architectural framing.
- **Proposed action**: Identify the case study (e.g. "Man Group's published account of their internal `arctic`/`man-tech` platform" or the QuantHouse / WorldQuant Brain case studies, or Bloomberg's 2024 BUY-side AI piece), or remove the quoted phrasing and replace with paraphrased framing that does not imply a single identifiable source.

### Finding 1.4
- **File**: `src/02-key-ideas.md`, line 87 (and `src/09-ml-platform.md`, line 47)
- **Quote**: "look-ahead bias, which the quantitative-finance literature names consistently as the single most common cause of strategies appearing profitable in backtests and failing in production"
- **Issue**: "The single most common cause" is a strong empirical claim about the literature without a single literature reference. The claim may well be defensible, but as written it is presented as established fact.
- **Load-bearing**: Yes — point-in-time correctness is one of the ten architectural bets, and its motivation rests entirely on this claim.
- **Proposed action**: Soften to "is consistently identified in the quantitative-finance literature as a leading cause" and add a citation, e.g. Bailey & López de Prado, "The Probability of Backtest Overfitting" (2014), or López de Prado, *Advances in Financial Machine Learning* (Wiley 2018), Ch. 11–13 on backtest pitfalls.

### Finding 1.5
- **File**: `src/05-architecture.md`, line 47
- **Quote**: "FastAPI ... dominant default in 2026 with production deployment at OpenAI, Anthropic, Microsoft"
- **Issue**: The naming of three specific organisations as production users of FastAPI is a strong, specific claim with no citation. Some of these are plausibly true and some are publicly stated, but none is sourced inline.
- **Load-bearing**: No — the FastAPI choice is defended on independent grounds (ecosystem, hiring pool). The org-name list is decorative.
- **Proposed action**: Either cite FastAPI's own "Sponsors and Users" page or Sebastián Ramírez's published interviews/talks, or remove the named-org list and replace with "widely adopted across the Python ecosystem, including by major AI labs."

## Check 2: Missing source attributions

### Finding 2.1
- **Location**: `src/05-architecture.md`, line 51
- **Claim**: "Polars ... 5–30× faster than pandas at typical workloads"
- **Proposed source**: Pola.rs official benchmarks page (`pola.rs/benchmarks`) or H2O.ai's `db-benchmark` results (which Polars publishes). For peer-reviewed, the comparative benchmarks in *PVLDB*'s 2023 columnar engines survey.
- **Rationale**: The Polars project itself maintains the canonical comparison benchmarks; citing the project page is the convention. The "5–30×" range is specific enough to need a source.

### Finding 2.2
- **Location**: `src/05-architecture.md`, line 120 (and echoed in `src/01-executive-summary.md` line 37)
- **Claim**: "uv (Astral) — 10–100× faster than pip/poetry"
- **Proposed source**: Astral's official launch blog post for uv (`astral.sh/blog/uv`) and the project README on GitHub (`astral-sh/uv`), which publish the comparative benchmarks.
- **Rationale**: The "10–100×" figure is Astral's own published claim; citing the source it came from is straightforward and authoritative.

### Finding 2.3
- **Location**: `src/02-key-ideas.md`, line 51
- **Claim**: "PGMQ handles tens of thousands of messages per second"
- **Proposed source**: Tembo's PGMQ benchmark blog post (`tembo.io/blog/pgmq-benchmarks`) or the upstream `pgmq/pgmq` GitHub README's performance section.
- **Rationale**: PGMQ's throughput ceiling is the load-bearing claim that justifies it as a Kafka substitute for the target market. Tembo, the project's primary maintainer, publishes the benchmark.

### Finding 2.4
- **Location**: `src/05-architecture.md`, line 131
- **Claim**: "Astral's continued stewardship (now within OpenAI's Codex team) secures its trajectory"
- **Proposed source**: Anthropic's or Astral's public announcement of the acquisition / partnership, if such a thing exists. As of the document's claimed cutoff this should be linkable.
- **Rationale**: The factual claim "Astral is now within OpenAI's Codex team" is verifiable and ought to be cited so the reader can confirm. It is also a load-bearing claim for the "uv's trajectory is secure" argument. If the claim cannot be sourced, it must be removed — assertions about acquisitions/team-membership are exactly the kind of fact a sophisticated reader will check.

## Check 3: Internal consistency

### Finding 3.1
- **Locations**: `src/02-key-ideas.md` line 59, `src/05-architecture.md` line 141, `src/13-observability.md` line 61 (in-process asyncio model) versus `src/01-executive-summary.md` line 19, `src/02-key-ideas.md` lines 29 and 37, `src/07-application.md` lines 9–17, `src/10-infrastructure.md` lines 13 and 25 (separate Cloud Run worker services per role)
- **Contradiction**: The blueprint says two different things about where projector/worker code runs:
  - Key Ideas §5: "projectors run inside the main application process as asyncio tasks, sharing connection pools and logging context; they are not separate services."
  - Architecture §Container view and §Data flow: "Projection workers, running as asyncio tasks within the same process, consume their respective queues..."
  - Observability §Distributed tracing: "all within a single process and a single database, which means traces are usually short."
  - Application §Single image, multiple roles, plus the role table, plus the rationale section: workers are deployed as **separate Cloud Run services** stamped from the same image, autoscaled by queue depth, explicitly contrasted against the "single-process kitchen sink" anti-pattern.
  - Infrastructure §Per-tenant resource topology: "Cloud Run services (`worker-*`) — One Cloud Run service per worker role, each stamped from the same image with a different `ROLE` env var."
  This is the single most important contradiction in the document. The "single-image-multi-role" pattern is one of the ten architectural bets, and Chapter 7 explicitly rejects the in-process asyncio-task pattern as a "single-process kitchen sink" — but Chapters 2, 5, and 13 describe exactly that pattern.
- **Proposed resolution**: The single-image-multi-role-with-separate-Cloud-Run-services description (Chapters 1, 7, 10) is the canonical position and is the one Igor explicitly corrected during development (Chapter 2 line 35 attests to this). Update the contradicting passages:
  - `src/02-key-ideas.md` line 59: rephrase "projectors run inside the main application process as asyncio tasks" → "each projector role runs as a dedicated worker process from the same image, with internal concurrency implemented via asyncio tasks within that worker; projector workers are not co-resident with the API."
  - `src/05-architecture.md` line 141: "Projection workers, running as asyncio tasks within the same process" → "Projection workers, running as separate Cloud Run services (one per projector role) stamped from the same image..."
  - `src/05-architecture.md` lines 14–24 (container view) currently lists "the application container ... a Python process hosting ... the read-model projectors, the pipeline workers, the training orchestrators, and the inference endpoints." Replace with the role-set described in Chapter 7's role table.
  - `src/13-observability.md` line 61: replace "all within a single process" with "across the small set of single-purpose worker services (api, worker-proj-*, worker-pipeline-*, scheduler), all sharing the same database."

### Finding 3.2
- **Locations**: `src/02-key-ideas.md` lines 69 and 85, `src/09-ml-platform.md` line 49 (use `_knowable_at`) versus `src/08-data-platform.md` lines 118–120 (use `_valid_from` and `_valid_to`)
- **Contradiction**: The bi-temporal column scheme is named two different ways. Key Ideas and ML Platform describe a single `_knowable_at` column on every silver/gold row. Data Platform describes a `_valid_from` / `_valid_to` pair, which is a different (validity-interval) bi-temporal pattern. A reader cannot tell whether the platform stores a single timestamp at which the datum became knowable, an interval over which it is valid, or both.
- **Proposed resolution**: Pick one and unify. Both patterns are legitimate and they are not equivalent: `_knowable_at` is the system-time / transaction-time half of bi-temporal, while `_valid_from` / `_valid_to` is the business-time / valid-time half. Recommended: keep both, since the document's stated requirement (point-in-time correctness against vendor-late-arriving data plus correction-as-new-row semantics) needs both. Update Chapter 8 §Point-in-time correctness to specify all four columns (`_valid_from`, `_valid_to`, `_knowable_at`, and the original business-event timestamp) and explain how training-extraction `as_of` filters against `_knowable_at` while temporal queries use `_valid_from`/`_valid_to`. Update Key Ideas §8 and ML Platform §Point-in-time correctness to use the same vocabulary.

### Finding 3.3
- **Locations**: `src/03-design-brief.md` line 29 ("Near-monolithic application. One Python process hosts the API, the command handlers, the read-side projectors, the pipeline workers, and the serving endpoints. One deployable unit") versus `src/07-application.md` lines 9–17 (nine distinct roles deployed as nine distinct Cloud Run services)
- **Contradiction**: The Design Brief says the application is "one Python process" and "one deployable unit." The Application Architecture chapter says it is one image deployed as nine separate services. These are not the same architectural shape.
- **Proposed resolution**: Update Goal 6 in `src/03-design-brief.md` to: "Near-monolithic application. One codebase, one Docker image, one test suite, one mental model — deployed as a small set of single-purpose services (API, projectors, pipeline workers, scheduler) selected at startup by an environment variable. Workers scale independently of the API." This preserves the "monolith for development; polymorphic at runtime" framing that the rest of the document uses.

### Finding 3.4
- **Locations**: `src/05-architecture.md` line 122 ("**pyright** (or Astral's **ty** once GA)"), `src/11-local-development.md` line 120 ("**pyright** ... CI fails on type errors") versus `src/11-local-development.md` line 51 ("Run ruff, mypy, and frontend linters") and `src/12-cicd-deployment.md` line 175 ("Type check — mypy or pyright for Python")
- **Contradiction**: The tech-stack table specifies pyright (with ty as an upgrade path). Two other places mention mypy as a current option. The Makefile target line in Chapter 11 says "ruff, mypy, and frontend linters" while the tooling-foundations section a few lines below in the same chapter says pyright. Which one runs in `make lint`?
- **Proposed resolution**: Architecture chapter is canonical (per the review brief). Replace "mypy" with "pyright" in `src/11-local-development.md` line 51 and in `src/12-cicd-deployment.md` line 175.

### Finding 3.5
- **Locations**: `src/08-data-platform.md` line 21 ("Accepted on-the-wire formats include CSV, JSON, and parquet") versus `src/08-data-platform.md` line 62 ("Expected format (CSV, parquet, JSON, fixed-width; delimiters, encoding, header presence)")
- **Contradiction**: The bronze section enumerates three accepted inbound formats; the file-contract section, eight pages later in the same chapter, adds a fourth (fixed-width). A reader trying to scope the ingestion implementation cannot tell whether fixed-width is supported.
- **Proposed resolution**: Decide whether fixed-width is in scope. If yes, add it to line 21's enumeration. If no (recommended for Phase 1–3 scope), remove it from line 62's example and replace with a parenthetical about delimiter/encoding/header-presence options for CSV.

### Finding 3.6
- **Locations**: `src/05-architecture.md` line 47 (Litestar rejected because "ecosystem maturity outweighs raw throughput at the target request scale") versus `src/05-architecture.md` line 135 ("Litestar's raw throughput is higher, but the ecosystem, documentation, and hiring pool for FastAPI are decisively larger, and the throughput gap is irrelevant at realistic request rates for this market")
- **Contradiction**: Two near-identical statements appear in the same chapter. They are not contradictory in content but are redundant; the second adds "hiring pool" and "decisively larger" but otherwise duplicates. A reader notices the repetition and wonders which is the canonical statement.
- **Proposed resolution**: Keep the more substantive line 135 statement in the "Why these choices over common alternatives" subsection. Trim the rationale cell at line 47 to "Async-native, Pydantic-v2 integrated, first-class OpenAPI; ecosystem dominance discussed below." Cross-references avoid duplicate-statement drift.

### Finding 3.7
- **Locations**: `src/10-infrastructure.md` line 16 ("Cloud SQL / AlloyDB instance — Postgres with AGE, TimescaleDB, PGMQ, pg_cron extensions") and `src/05-architecture.md` line 17 ("Cloud SQL is the default; AlloyDB is required if AGE or PGMQ are not available on Cloud SQL's supported extension list in the deployment region") versus `src/02-key-ideas.md` line 45 ("Cloud SQL or AlloyDB in production")
- **Contradiction**: Architecture chapter is precise about when AlloyDB is required and why; Infrastructure chapter and Key Ideas chapter present them as interchangeable. A reader wanting to know which one the Terraform module actually provisions cannot tell. The Terraform tree at `src/10-infrastructure.md` lines 99–125 does not disambiguate (`database.tf # Cloud SQL / AlloyDB`).
- **Proposed resolution**: State the rule once (Architecture chapter) and reference it elsewhere. In the Infrastructure chapter resource table, change "Cloud SQL / AlloyDB" → "Cloud SQL by default, AlloyDB where required (see Architecture §Container view)." In the Terraform comment, the same pointer.

## Check 4: Logical consistency

### Finding 4.1
- **Location**: `src/15-roadmap.md`, line 42 (Phase 1 scope: "First production tenant provisioned via the Terraform module and live") versus line 99 (Phase 5 scope: "Automated tenant provisioning — operator fills a form, control plane drives Terraform, tenant is live within its SLA")
- **Issue**: Phase 1's acceptance condition requires a production tenant to be live. Phase 5 introduces the control plane that drives Terraform for provisioning. The dependency is fine — Phase 1 provisions the first tenant manually via Terraform — but the document does not say so explicitly. A reader following the prerequisites graph thinks "how is Phase 1 supposed to provision a tenant before the control plane exists?" and is left to infer the answer.
- **Proposed fix**: In Phase 1 scope, change "First production tenant provisioned via the Terraform module and live" to "First production tenant provisioned by an engineer running `terraform apply` directly against the per-tenant module (the control plane that automates this is introduced in Phase 5)."

### Finding 4.2
- **Location**: `src/09-ml-platform.md`, line 76 ("transitions MLflow's model stage from staging to production") and line 96 ("reads a registry of production-stage models from MLflow")
- **Issue**: The blueprint specifies MLflow 2.x (Architecture chapter line 74). MLflow's Model Stages API was deprecated in MLflow 2.9 in favour of Model Aliases, and in MLflow 3.x stages have been removed entirely. A document targeting "best-in-class as of 2026" that pins MLflow 2.x and uses stages should at minimum acknowledge this (will the platform stay on 2.x indefinitely? migrate to aliases? stay on stages until forced off?).
- **Proposed fix**: Either pin MLflow to a specific minor version that still supports stages and explain why; or replace "model stage" with "model alias" terminology and update the registry-API description; or add a short paragraph in the MLflow section noting the stages-vs-aliases evolution and the platform's stance.

### Finding 4.3
- **Location**: `src/05-architecture.md`, line 21 ("MLflow tracking server ... Backed by the same Postgres instance (separate schema)") versus `src/09-ml-platform.md`, line 65 ("It shares the Postgres instance with the main application (distinct schema) and uses the tenant's GCS bucket for artefact storage. Its upgrade cadence is decoupled from the main application")
- **Issue**: The two statements are consistent in fact but the second introduces a subtle problem the document does not resolve: if MLflow shares the Postgres instance with the main application, an MLflow upgrade that requires a Postgres extension or a Postgres major-version bump is no longer "decoupled." The independence claim is conditioned on a property (schema-only sharing with no version coupling) the chapter does not name.
- **Proposed fix**: Add one sentence to the ML Platform §MLflow section: "Decoupling holds for MLflow application versions; a database engine version change requires coordination because the Postgres instance is shared. Such changes are rare and managed at the tenant-upgrade level."

### Finding 4.4
- **Location**: `src/12-cicd-deployment.md`, line 73 ("Security scan: dependency vulnerability scan via `uv` (upcoming first-party audit)")
- **Issue**: The pipeline relies on a security-scan capability described as "upcoming." This is a logical gap — the pipeline cannot in fact run a uv-native audit if the feature does not yet exist. The reader does not know whether this is a "skip until uv ships it" or a "use pip-audit / safety in the meantime" or a "this gates merging."
- **Proposed fix**: State the interim. Suggested replacement: "Security scan: dependency vulnerability scan via `pip-audit` against the uv-resolved environment (to be replaced by `uv audit` once Astral ships it as a first-party command); GitHub Dependency Review on the lockfile; secret-pattern scan via `trufflehog` or equivalent."

## Check 5: Hedging and over-confidence

### Finding 5.1
- **Location**: `src/05-architecture.md`, line 130
- **Category**: over-confidence
- **Current text**: "**Polars over pandas**: for anything but legacy compatibility, Polars is faster, has better memory characteristics, and its lazy API produces query plans that optimise across operations."
- **Proposed text**: "**Polars over pandas**: for the workloads typical of this platform — bulk silver/gold transformations, group-bys, joins on multi-million-row dataframes — Polars is materially faster than pandas and has substantially better memory characteristics. Its lazy API produces query plans that optimise across operations. Pandas remains acceptable at integration points with libraries that require it."

### Finding 5.2
- **Location**: `src/02-key-ideas.md`, line 91 ("Revisit when: never.")
- **Category**: over-confidence
- **Current text**: "Revisit when: never."
- **Proposed text**: "Revisit when: an as-yet-unforeseen workload demonstrates that the bi-temporal modelling overhead exceeds its benefit — none anticipated for the target customer segment."
- **Note**: The same construction appears at `src/02-key-ideas.md` line 25 ("Revisit when: never. This is the governing constraint."). For local-first the absolute wording is defensible because the document explicitly designates it the governing constraint. For point-in-time correctness, "never" is over-confident; soften.

### Finding 5.3
- **Location**: `src/02-key-ideas.md`, line 35
- **Category**: over-confidence (mixed with editorial)
- **Current text**: "It is the pattern Igor explicitly corrected during this blueprint's development."
- **Proposed text**: Remove the sentence. A blueprint going to a Morgan Stanley contact and to Jenny Lin should not contain first-name references to its author or annotations about the document's drafting history. Replace with: "The single-process pattern is rejected on the same grounds as scattered serverless: it sacrifices the runtime independence that distinguishes a production worker pool from a prototype."

### Finding 5.4
- **Location**: `src/02-key-ideas.md`, line 41 ("Revisit when: never for the overall shape.") and `src/02-key-ideas.md`, line 81 ("Revisit when: never for new model onboardings.") and `src/02-key-ideas.md`, line 91 ("Revisit when: never.")
- **Category**: over-confidence (cumulative)
- **Current text**: Three of the ten "Revisit when" cells in Key Ideas are answered "never." A reader counting the answers wonders whether the section is performing the function it sets up (an honest list of revision triggers) or asserting the architecture is permanent.
- **Proposed text**: Keep "never" for at most one of the ten (the local-first constraint, where the document has explicitly framed it as the governing constraint). Replace the other two with concrete-but-distant triggers, e.g. for §3 single-image: "Revisit if the team's per-role release cadences diverge enough that they share fewer than half their dependencies; until then the shared image dominates."

## Non-findings

The following items were inspected and are acceptable as written:

- **Tenancy model.** The silo-only stance is consistent across executive summary, design brief, key ideas, tenancy chapter, infrastructure chapter, and security chapter. The lone `tenant_id` mention (`src/13-observability.md` line 20) is correctly framed as "for local and non-silo contexts; implicit at the project level in production" and does not contradict the silo position. The "row-level" mention in `src/08-data-platform.md` line 98 refers to row-level Pydantic validation of a small dataset, not row-level security on a multi-tenant table.
- **Authentication flow.** OIDC-to-session-JWT flow is described once in the tenancy chapter and is referenced consistently in the security and observability chapters. No competing flow is introduced anywhere.
- **File-based ingestion vocabulary.** The four-pattern enumeration (scheduled pull / push drop to GCS / push drop via SFTP / customer-operated drop) is established in `src/08-data-platform.md` and the roadmap (`src/15-roadmap.md` line 68) uses the same vocabulary.
- **Event flow / single-transaction CQRS.** The single-transaction (events + state + queue) description is consistent across Key Ideas, Architecture, and Application chapters. PGMQ-as-shared-database is repeated coherently.
- **Container base image.** "Chainguard Python or Distroless" is repeated identically in three places (Architecture, CI/CD, Security).
- **Secrets handling.** Consistent across Tenancy, Infrastructure, Security, and CI/CD chapters: Secret Manager in cloud, `.env` locally, no static credentials in images or git.
- **Roadmap dependency graph.** The textual prerequisites for Phases 0–6 are internally consistent with the dependency-graph paragraph at the end of the roadmap chapter, with the single qualification noted in Finding 4.1.
- **Cloud Run vs Cloud Functions.** Cloud Functions appears only as a rejected alternative ("Identity Platform's blocking-function model fragments code across Cloud Functions"); it is not introduced as a deployment target anywhere.
- **Pipeline performance numbers.** The "five to eight minutes" PR pipeline in `src/11-local-development.md` line 98 and `src/12-cicd-deployment.md` line 157 match. The "three to six minute" integration stage at `src/12-cicd-deployment.md` line 93 is consistent with the larger PR-pipeline budget that contains it.
