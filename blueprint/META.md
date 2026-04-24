# Meta — How This Blueprint Was Produced

This file describes the process that produced the Quant Platform Blueprint. It is an honest account of the collaboration, not a reconstruction of a "proper" process. Future maintainers can use it to understand why specific choices were made and which areas deserve the closest scrutiny in revision.

## Origin

The blueprint originated in a conversation about architecture for a friend of a mutual contact — a quantitative engineer at Morgan Stanley building a platform to help other hedge funds productionalise their quant models. The original ask was framed as peer-to-peer architectural help: "here is the shape of the customer, what would you build?"

The conversation proceeded interactively, not as a formal requirements gathering. Decisions emerged as the conversation progressed. Several architectural positions that appear in the final document were not in the initial framing; they were introduced as constraints the user stated during the discussion. Examples:

- Silo tenancy was introduced partway through, after the conversation had spent time on multi-tenant row-level security patterns. Once stated, it simplified large portions of the architecture.
- The local-first constraint — that every production behaviour must be reproducible on a developer laptop — was stated as a "golden rule" after several services (Cloud Workflows, Cloud Tasks) had already been discussed as candidates. The rule retroactively disqualified those services.
- The preference for a near-monolithic Python application over scattered serverless was stated after an early proposal that split logic across multiple Cloud Run services. The proposal was revised in place.
- The preference for `uv` as the Python package manager and for the Astral tooling ecosystem (ruff, pyright/ty) was stated explicitly by the user and applied across the document.

This iterative emergence of constraints is normal for a conversation with a domain expert. The blueprint captures the end state, not the path.

## Research inputs

Web searches were performed on specific topics to ground the document in current industry practice:

- **Hedge fund quant model infrastructure (2026)** — confirmed the prominence of quant strategies in 2026 hedge fund allocation, the growing role of separately managed accounts, and the emergence of internal developer platforms as a deployment pattern.
- **Point-in-time correctness and bi-temporal architecture** — confirmed look-ahead bias as the most-commonly-cited cause of backtest-to-production strategy failure, and bi-temporal schemas as the textbook defence.
- **Backtesting and research-to-production parity** — confirmed the standing of QSTrader, LEAN, and vectorbt as current leading open-source frameworks in the space.
- **Python packaging and tooling (2026)** — confirmed `uv` and the Astral ecosystem as the current default for new Python projects, and confirmed Astral's stewardship under OpenAI's Codex team.
- **Web framework selection** — confirmed FastAPI's continued dominance as the default greenfield async Python web framework, with Litestar noted as a strong performance-focused alternative.
- **Time-series forecasting** — confirmed the Nixtla suite (StatsForecast, MLForecast, NeuralForecast, HierarchicalForecast) and Darts as the current leading Python libraries for time-series forecasting.

Sources used are listed in the final status message produced when the document was completed. The blueprint text itself does not currently include inline citations; this is a gap identified for the review stage.

## Architectural positions that emerged from the user

Several positions in the document are not derived from industry research but from the user's domain judgement. These are explicitly the user's preferences and should be understood as such rather than as neutral architectural defaults:

1. The near-monolith preference over fine-grained serverless
2. The local-first "golden rule" as non-negotiable
3. Postgres-centric data plane using extensions rather than dedicated products (Kafka, Neo4j, Kdb)
4. `uv` as the package manager
5. Preference for open-source and portable components over managed cloud-proprietary services where both are viable
6. The conviction that silo tenancy is the right model for the hedge-fund market specifically
7. The structural rejection of scheduled calendar timelines in the roadmap on the grounds that the implementor is agentic rather than a human team

Each of these is defensible on its merits, and the document argues for each, but a reviewer evaluating the document should understand that they are chosen positions rather than derived conclusions.

## What the document does not do

- **It does not benchmark alternatives quantitatively.** Claims like "Polars is 5–30× faster than pandas" are stated as received wisdom from the relevant library's documentation and benchmarks; no independent benchmark was run for this document.
- **It does not cite inline sources.** Industry research informed the content but is not cited at the point of use. The review stage is expected to surface this as a finding and propose specific citations.
- **It does not include example code.** Per an explicit user directive during the conversation ("stop writing code this is high level architecture"), the document is descriptive rather than prescriptive at the code level. Small fragments of shell, YAML, or SQL appear only where they clarify the architecture.
- **It does not include security certifications.** The security chapter describes the posture; a formal SOC 2 readiness audit is out of scope.
- **It does not include per-customer operational runbooks.** Runbooks are a product of operating the platform, not a precondition for describing it.

## Structure rationale

The document proceeds from high-level to detailed:

1. **Executive summary** — single-chapter overview for stakeholders making a go/no-go decision
2. **Key ideas** — the ten architectural bets, argued at a depth sufficient to defend against "why not X?"
3. **Design brief** — the goals, personas, and constraints in full
4. **Environment flavours** — the deployment topologies supported
5. **System architecture** — the container view, components, technology stack
6. **Tenancy and authentication** — silo model, OIDC federation, role mapping
7. **Application architecture** — FastAPI near-monolith, CQRS, worker model
8. **Data platform** — medallion pipeline, file-based I/O, point-in-time correctness
9. **ML platform** — training, MLflow, serving, research-to-production parity
10. **Infrastructure** — per-tenant Terraform, control plane, GCP resources
11. **Local development** — the golden rule, docker-compose stack, testing strategy
12. **CI/CD and deployment** — GitHub Actions pipeline, blue/green, release testing
13. **Observability and operations** — logging, metrics, alerting, incident response
14. **Security and compliance** — threat model, tenant isolation, audit posture
15. **Build sequence** — phases with prerequisites and acceptance conditions

A reader evaluating a specific aspect can read the relevant chapter directly. A reader evaluating the platform as a whole reads the executive summary and the key ideas, then drills into the chapters that answer their specific questions.

## Build and rebuild

The deliverable is a PDF assembled from markdown sources and Mermaid diagrams.

**Toolchain:**

- `pandoc` — markdown-to-LaTeX-to-PDF orchestration
- `mmdc` (mermaid-cli) — renders Mermaid source to vector PDF
- `tectonic` — lightweight modern LaTeX engine, fetches packages on demand

**Build:** `make pdf` in the `blueprint/` directory. Produces `output/blueprint.pdf`.

**Clean:** `make clean` removes rendered diagrams and the PDF output.

**Add a chapter:** create a new file in `src/` with a numeric prefix that sorts into the desired position. Add diagrams in `diagrams/` with a matching prefix; they render to `diagrams/rendered/` and are referenced from the markdown as `![caption](diagrams/rendered/NN-name.pdf){width=95%}`.

**Change technology choices:** the canonical list lives in `src/05-architecture.md` in the technology stack tables. Other chapters refer to the choices made there; propagating a change means editing the tables and then searching for any other chapter that needs updating.

## Known maintenance concerns

1. **Inline citations.** Industry claims are not cited. The review stage is expected to surface this systematically; applying those fixes is the next editing pass.
2. **Version drift.** Library versions (Python 3.12, Postgres 16, MLflow 2.x, React 19) are stated but will age. A periodic re-read should confirm or update them.
3. **Regulatory detail.** The security and compliance chapter names regulators and regimes (SEC, CFTC, FINRA, SOC 2, ISO 27001) at a high level. A customer-facing version of the document should either substantiate these references or remove them.
4. **BYOC specifics.** The BYOC model is described but not implemented in the reference Terraform module shape. When a specific customer demands BYOC, the Terraform module will need to be split into platform-provisioning-only and customer-provisioning-only portions, and this document should reflect that split.
5. **Data-vendor integrations.** Specific vendor names (Bloomberg, Refinitiv, Factset, Polygon) are deliberately absent. Customer-facing presentations will likely want vendor-integration examples; these should be added in a separate appendix rather than embedded in the core architecture.

## Provenance of specific sections

| Section | Primary origin |
| :--- | :--- |
| Silo tenancy | User-stated preference, argued here |
| Local-first rule | User-stated preference, enforced throughout |
| Near-monolith preference | User-stated preference |
| Postgres-centric data plane | Joint architectural reasoning |
| CQRS with PGMQ | Joint architectural reasoning |
| Medallion architecture | Industry-standard; adapted to file-first for hedge-fund context |
| Point-in-time correctness | Industry research-backed |
| Research-to-production parity | Industry research-backed |
| Blue/green via Cloud Run | GCP-native feature; applied straightforwardly |
| Control plane | Direct consequence of silo tenancy at scale |
| `uv` and Astral tooling | User-stated preference, confirmed by current industry positioning |
| FastAPI, Polars, Pydantic v2 | Current best-in-class for Python in 2026 |
| Nixtla suite for time series | Current best-in-class for Python time-series forecasting |
| Roadmap without calendar | User-stated directive (implementor is agentic) |

Future revisions should keep this table current as new sections are added.

## Next steps

1. Run the review agent per `REVIEW.md`.
2. Address findings, particularly load-bearing missing citations.
3. Re-render the PDF (`make pdf`).
4. Share with intended audience (Morgan Stanley friend via Jenny Lin).
5. Iterate based on their feedback, treating this document as v1 of a living artefact.

The blueprint is a starting point for a conversation with the reader, not a finished product. Its value comes from giving the reader a concrete position to agree with, disagree with, or extend.
