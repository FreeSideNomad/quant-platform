---
title: Quant Platform — Positioning
date: 2026-04-21
status: draft
purpose: >
  The document the blueprint and PRD lacked. Answers "what is this product, who buys it,
  why do they buy it instead of SigTech / Domino / Palantir / Databricks / building it themselves,
  and what are we not." Anchors marketing, demo narrative, NotebookLM video, and any sales conversation.
audience: internal (vendor team) — informs how the platform is described externally
---

# Quant Platform — Positioning

## 1. The one-sentence pitch

> **An open-source-first, silo-tenant productionalization platform that lets a quant ship a model from notebook to audited production without an engineering hand-off, and lets their fund pass an LP's operational due-diligence questionnaire from screenshots in the UI.**

Every other section of this document is the proof, the comparison, or the boundary of that sentence.

If you cannot say that sentence in a meeting and have the listener nod, the rest is wasted. The sentence is the test. Every chapter of the blueprint, every section of the PRD, every screen of the UI either supports that sentence or is engineering self-talk that should not be in customer-facing materials.

## 2. Who buys this

### 2.1 Primary buyer — the head of quant technology at a mid-market systematic shop

- AUM band: $500M to $5B.
- Team size: 20-80 people, with 8-25 quants and 4-12 engineers.
- Current state: a sprawling internal Python monorepo, 4-7 years of accumulated infrastructure debt, recent ODD questionnaire from an LP that exposed gaps the team has been meaning to close for two years.
- Has CFO authorisation for $200-400k/year on external platform spend if it credibly replaces engineering work the team is currently doing badly.
- Has been quoted by SigTech and either (a) found the price prohibitive, or (b) been told they are too small to be a serious customer, or (c) refused on grounds that their data and code cannot leave their cloud.
- Has talked to Databricks and concluded it is a data platform with ML attached, not the other way round.
- Has looked at Palantir Foundry and concluded the sales motion (six-figure annual minimums, forward-deployed engineers, multi-quarter implementations) is not for a fund of their size.
- Has considered Domino and concluded it is a generic enterprise MLOps tool that doesn't speak quant; would have to bolt on backtesting, walk-forward, factor decomposition, and audit chaining themselves.
- Has thought about hiring two more engineers and building it themselves and concluded the headcount is unavailable, the timeline is two years, and the team's existing engineers want to do alpha research not infrastructure.

This is the buyer the platform is shaped for. The PRD's Morgan persona (§2.1) is this buyer.

### 2.2 Secondary buyer — the LP allocator running ODD on a quant manager

Not directly a buyer of the platform but the *validator* that justifies the manager's purchase. When the manager can answer the LP's tech-discipline questionnaire by sharing a screen instead of writing a 14-page document, the manager renews the LP's allocation. The platform's audit trail, lineage drill-downs, model-promotion gates, and PBO/DSR reporting are designed so the LP's questions answer themselves from the UI. The PRD's Priya persona (§2.2) is this validator.

### 2.3 Buyers we do *not* target

- **Enterprise-tier hedge funds with $20B+ AUM and 100+ engineers.** They build their own. They will not buy externally; they may license open-source components from us, but they are not customers.
- **Retail systematic traders.** Floor cost of silo tenancy is too high; QuantConnect and Alpaca serve this segment.
- **Multi-asset macro funds whose primary workflow is discretionary-with-systematic-overlay.** Their workload is dominated by macro nowcasting and scenario analysis, not by the cross-sectional alpha workflow this platform is shaped for. Phase-2 customer at best.
- **Funds whose engineering team has just been told to build a platform in-house and has political momentum to do so.** They will not switch until the in-house build hits a wall, which typically takes 18-30 months. Stay in light contact, do not pursue.
- **Funds entirely on AWS who refuse GCP.** GCP is the default deployment substrate; AWS support is feasible (the architecture transfers) but is a per-customer engineering investment, not a v1 capability.

## 3. What we are NOT (explicit anti-positioning)

The most expensive marketing mistake in this category is being mistaken for one of the bigger competitors. To prevent this, here is the explicit list of what this product is not.

- **Not Databricks.** We do not host petabyte data lakes; we do not run Spark; we do not target the broad data-engineering org. Postgres handles our customer's operational data because the customer's actual data volume fits in Postgres.
- **Not Palantir Foundry / AIP.** We do not have forward-deployed engineers. We do not do multi-quarter implementations. We do not target multi-domain enterprises. Our sales motion is mid-market self-serve trial → paid pilot → annual contract; it is not enterprise consulting.
- **Not Domino Data Lab.** We are not generic MLOps. PBO/DSR/walk-forward/bi-temporal/factor-decomposition/audit-chaining are the *defaults*, not configurable add-ons. A Domino customer who tried to make Domino do what we do would spend a year integrating and lose the opinionated discipline that comes from a quant-native baseline.
- **Not SigTech.** We are silo-tenant by default; SigTech is multi-tenant cloud SaaS (verify, but their public posture). We are open-source-first; SigTech is proprietary. Our customer's data and code stay in their cloud; SigTech's customers send theirs to SigTech's cloud. We are mid-market priced; SigTech is enterprise priced.
- **Not WorldQuant Brain or QuantConnect.** Those are crowdsourced-alpha or retail-trading platforms. We are infrastructure for managers who already have their own alpha and need to productionalize it.
- **Not a notebook environment.** Marimo and Jupyter exist; we embed them, we do not rebuild them. The notebook is one screen of the platform, not the platform itself.
- **Not a backtest library.** vectorbt and QSTrader exist; we wrap them with PBO/DSR/walk-forward enforcement. The library is a building block, not the product.
- **Not a research environment.** Researchers do their early-stage exploration anywhere — we accept research output, we do not dictate research process.
- **Not a custom-orchestration shop.** We do not build bespoke pipeline plumbing. The platform's view-of-state is Dagster's asset graph — Dagster is the dominant open-source asset-orchestration platform and we use it where competitors either roll their own or expose no orchestration layer at all. The SDK's `register()` writes a Dagster asset definition; the Dagster UI is exposed read-only through the platform's BFF; quants get visual lineage as a side effect rather than as a feature we hand-built.
- **Not an AI-first hedge fund or a hedge fund itself.** We are infrastructure that hedge funds use. We do not have proprietary alpha, we do not invest, we do not take fund management fees.

## 4. The three load-bearing differentiators

If a prospect remembers nothing else, they should remember these three. Anything else is supporting.

### 4.1 Differentiator 1 — Silo + BYOC by default

The architecture provisions a dedicated GCP project per tenant. There is no shared database, no shared application process, no shared secrets vault. For BYOC customers, the project lives in the customer's own GCP organisation; the vendor has limited-scope deployment access and no read access to data. The customer's data and code never leave their cloud perimeter.

**Why it matters:**
- Hedge fund security teams reject multi-tenant SaaS for production-grade workloads at high frequency.
- LP ODD questionnaires increasingly ask about data residency and tenancy isolation.
- SMA structures push managers toward per-mandate deployment patterns where each mandate's data stays inside the LP's IT perimeter.
- "We can run this in your cloud" is a sales line that converts to demo with a frequency that "we are SOC 2 certified multi-tenant" does not.

**What it costs:** Higher per-tenant infrastructure floor; control plane required to manage the fleet; deployment time per new tenant measured in tens of minutes not seconds.

**Why competitors don't do it:** Operationally expensive; multi-tenant SaaS economics are easier; SigTech and Domino chose differently and would need to rearchitect to match.

### 4.2 Differentiator 2 — Open-source-first stack

Polars (data frames), Postgres + extensions (operational substrate), MLflow (registry), Dagster (asset orchestration), FastAPI (API), Pydantic (validation), Vite + React + Tailwind + shadcn (UI), uv (packaging), Cloud Run (runtime). Every load-bearing component is open-source with permissive licensing. Customers can in principle pull their stack out of our managed offering and run it themselves on equivalent infrastructure.

**Why it matters:**
- Vendor-lock-in objection is real and frequent in hedge-fund procurement. "What happens when you raise prices 30% in year three?" is a question every CFO asks. Our answer: "You have the source code for our application, you have the open-source components, you have the Terraform module, you can run this yourself on your existing GCP organisation."
- A fund that *wants* to bring infrastructure in-house in three years can do so without a re-platforming exercise.
- Aligns with the cultural bias of quant teams toward open-source tooling (most quants prefer scikit / PyTorch / pandas to vendor-proprietary equivalents).

**What it costs:** We give up the lock-in revenue model that proprietary competitors enjoy. We win on land/expand mechanics instead.

**Why competitors don't do it:** SigTech, Domino, Palantir all chose proprietary because the lock-in economics are stronger. Their existing customers are hostage; ours are not. We argue this is a feature, not a flaw.

### 4.3 Differentiator 3 — Quant-native, not generic-ML

PBO/DSR computed automatically on every backtest. Walk-forward validation enforced as a platform property; non-walk-forward models cannot be promoted. Bi-temporal data discipline (`_knowable_at` + `_valid_from` + `_valid_to`) enforced on every silver and gold row. CPCV (Combinatorial Purged Cross-Validation) as the cross-validation method, not standard k-fold. Factor decomposition (Carhart four-factor by default; Hou-Mo-Xue-Zhang q-factor as alternative) built into reporting. MLflow `pyfunc` discipline for research-to-production code parity. Cryptographic audit chain on the audit log, exportable to WORM GCS for regulated tenants.

**Why it matters:**
- A quant prospect can tell within 90 seconds of seeing the UI whether the platform was built by people who know the field. Generic MLOps tools fail this test instantly. Domino does not surface PBO/DSR; Palantir Foundry does not enforce walk-forward; Databricks does not have bi-temporal data as a first-class concept. Building these on top of those platforms is possible but it is months of integration work that the customer pays for in time, not years of platform discipline.
- LP ODD questionnaires ask quant-specific questions. A platform that answers them by default is more credible than one where the manager has to bolt on the answers.

**What it costs:** Narrower TAM. We turn away the "we have an ML platform that happens to do quant" customer and the "we have a quant team that wants to do non-quant ML on the same platform" customer.

**Why competitors don't do it:** Generic MLOps platforms target the broadest possible market. SigTech does some of this but is far less open about its methodology. Quant-native opinionated defaults are a *narrower* product, which is why the bigger competitors don't ship them.

### 4.4 Why three and not seven

The blueprint enumerates ten architectural bets; this document promotes three to differentiator status. The other seven (Postgres-centric, CQRS, single-image-multi-role, near-monolithic, customer IdP federation, blue/green deployment, control plane) are sound engineering decisions that *enable* the three differentiators but are not themselves customer value props. A customer never says "I bought this because it uses CQRS." Naming them as differentiators dilutes the message.

The three differentiators are also chosen to be **mutually reinforcing in marketing** but **independent in defensibility**. A competitor who matches one (say, by adding silo tenancy) does not automatically match the others. SigTech adding silo would still leave them proprietary and generic-ML-ish. Domino adding PBO/DSR would still leave them proprietary and multi-tenant. The three together are a moat; any one alone is a feature.

## 5. Head-to-head with each competitor

For each competitor, the customer-facing comparison: where they win, where we win, where we punt.

### 5.1 vs SigTech

**They win on:** Maturity (six years vs. our zero), customer count ($5T+ AUM vs. our zero), data curation depth, MAGIC AI agent layer, brand recognition in London/Europe, integration with existing data vendors, polished sales motion at the enterprise tier.

**We win on:** Silo + BYOC tenancy (their data stays in our customer's cloud, not ours; verify SigTech's tenancy model in customer conversations), open-source-first stack and the portability story it enables (including Dagster as the orchestration layer, where SigTech exposes no equivalent open primitive), mid-market price point, transparent quant-native methodology (PBO/DSR/CPCV documented in product UI, not behind a sales conversation), local-first developer workflow.

**Where we punt:** Top-tier enterprise customers ($10B+ AUM with deep multi-asset, multi-strategy stacks) — SigTech is a better fit; we do not contest that segment for v1.

**Sales line vs SigTech:** "SigTech is the right answer for $10B+ AUM funds that want a managed enterprise quant platform. We are the right answer for $500M-$5B AUM funds that need quant-grade discipline but want to keep the data and code in their own cloud, with an open-source stack they can take in-house if they choose."

### 5.2 vs Domino Data Lab

**They win on:** Generic enterprise MLOps maturity, brand recognition, Fortune 100 deployment scale, integration with non-Python tooling, customer-success and forward-deployed-engineer model.

**We win on:** Quant-native opinionated defaults (Domino is a generic MLOps tool that you would have to teach to do quant; we are quant-native out of the box), open-source stack vs. their proprietary one (Dagster as our orchestration layer rather than Domino's proprietary flow primitives), silo + BYOC by default, lower price point.

**Where we punt:** Non-quant ML workloads (we do not target medical imaging, NLP-for-customer-service, supply-chain optimisation; Domino is a better fit).

**Sales line vs Domino:** "Domino is the right answer if you have a generic enterprise data-science org with diverse ML workloads. We are the right answer if you are specifically a quant shop and you want PBO, walk-forward enforcement, bi-temporal data, and factor-decomposed reporting as defaults rather than as integration projects."

### 5.3 vs Palantir Foundry / AIP

**They win on:** Enterprise reach, multi-domain platform breadth, AI agent layer (AIP), forward-deployed-engineer model, government and defence presence, brand recognition, Model Studio (no-code training, Feb 2026 GA).

**We win on:** Sales motion (we are mid-market self-serve, they are enterprise consulting; we do not require a six-figure professional services engagement to deploy), quant-native focus (Foundry is multi-domain by design; we are quant by design), open-source vs. proprietary (Dagster as the orchestration substrate rather than Foundry's proprietary pipeline runtime), transparent pricing.

**Where we punt:** Customers who already have Foundry or who want a multi-domain enterprise platform spanning operations, supply chain, and analytics in addition to quant.

**Sales line vs Palantir:** "Foundry is the right answer for multi-domain enterprises with $5M+ annual platform budgets and a willingness to engage forward-deployed engineers. We are the right answer for hedge funds that want a focused product with a self-serve trial path."

### 5.4 vs Databricks

**They win on:** Data-engineering scale, Spark / Delta Lake ecosystem, MLflow contributions (they own MLflow; we use it), Lakehouse architecture for petabyte-scale customers, broad enterprise sales motion.

**We win on:** Right-sized for the customer's actual data volume (Postgres handles a $5B AUM hedge fund's operational data trivially; Spark is overkill), quant-native defaults vs. generic ML, silo + BYOC vs. Databricks workspace model, opinionated versus toolkit. Dagster (open-source asset orchestration) is the platform's pipeline layer, where Databricks customers stitch Workflows / Jobs / Delta Live Tables into the equivalent surface.

**Where we punt:** Customers with petabyte-scale data lakes (alt-data heavy, satellite imagery, social-media firehose). Databricks is a better fit; we do not contest that segment.

**Sales line vs Databricks:** "Databricks is the right answer if your bottleneck is data scale and you need Spark. We are the right answer if your bottleneck is research-to-production friction and your operational data fits in Postgres — which is almost every quant shop with under $20B AUM."

### 5.5 vs build-your-own (the most common comp)

The honest acknowledgment: the most frequent competitor in any platform-vendor sales conversation is "we are thinking about building it ourselves." Some customers do this well. Most do this badly. The honest argument:

**They win on:** Total control, no vendor relationship to manage, no procurement process, customisation to their exact workflow, retention of engineering knowledge, no recurring license cost.

**We win on:** Time-to-value (we ship in weeks; their build is 18-30 months minimum to reach what we provide on day one), opportunity cost (their engineering time goes to alpha-relevant work, not platform infrastructure), benchmark of best practices (we have read López de Prado; their team may not have), upgrade compounding (every feature we add is a feature they get without spending engineering on it).

**Where we punt:** Funds with $20B+ AUM and 50+ engineers — they have the capacity to build well. We do not target them.

**Sales line vs build-your-own:** "Building this yourself is reasonable if you are a $20B+ fund with 50+ engineers and a CTO with two years of patience. For a $500M-$5B fund with under 25 engineers, the maths does not work: 18 months of platform-engineering work that we provide on day one is a better outcome than 24 months of partial completion that you maintain forever."

### 5.6 vs Jenny Lin's platform (peer competitor)

Per memory, Jenny is building a parallel hedge-fund quant productionalization platform. Insufficient public information to compare specifically. The probable differentiation to emphasise: silo + BYOC, open-source-first, quant-native defaults — the same three differentiators that hold against the established competitors, since it is unlikely Jenny's platform matches all three. Verify in conversation when her product specifics become public.

## 6. The actual quant workflow today, mapped to platform value

This section is the proof that the product is *useful*, not just architecturally interesting. It maps the actual day-to-day work of a quant at a $1B-AUM systematic equity fund to where the platform helps and where it is neutral.

| Step | What the quant does today | What the platform does | Value level |
| :--- | :--- | :--- | :--- |
| 1. Open laptop, set up environment | Fights with conda / pip / poetry; Docker for some dependencies; takes hours-days | One `make demo-fresh` command; full local stack including Postgres, MinIO, mock OIDC, MLflow, in 5 minutes | **High** — eliminates a week of onboarding |
| 2. Connect to data | SSH / boto3 / Snowflake-CLI; per-source authentication; per-source schema discovery | Data is already typed, validated, point-in-time correct in the gold layer; Polars dataframe is a function call | **High** — eliminates a class of "where does this data come from" debugging |
| 3. Sample for exploration | Pandas; for big data, ad-hoc SQL pulls; format-juggling | Polars lazy; one query API across silver and gold | **Medium** — Polars itself isn't a moat, but the integration is |
| 4. Iterate feature code in notebook | Notebook cells; copy-paste between research and production; the function definitions slowly diverge | The notebook imports the same `features/` module the production serving path uses; one source of truth | **High** — eliminates train-serve skew as a class of bug |
| 5. Test feature on sample | Visual inspection; ad-hoc unit tests | Pandera schema validation runs automatically; integration tests against the local docker-compose stack | **Medium** — saves time, doesn't change the work fundamentally |
| 6. Commit to git | Git workflow | Git workflow (no platform addition) | **None** — table stakes |
| 7. Kick off real training | Slurm script / aws sagemaker create-training-job / internal kubernetes manifest; wait hours; check on it | One-click submission to Cloud Run Jobs (CPU) or Vertex AI Custom Training (GPU); the platform's view-of-state is Dagster's asset graph, so each fold is materialised as a Dagster asset and tracked automatically; MLflow records the run | **High** — eliminates a multi-day infrastructure burden per training campaign |
| 8. Review trained model | MLflow / internal dashboards / SHAP plots in another notebook | Run-detail UI shows metrics, walk-forward evidence, PBO/DSR, factor attribution, comparison to baseline — all in one screen; the same Dagster asset graph is exposed read-only through the BFF, so the quant gets visual lineage from bronze data to model version as a side effect | **High** — collapses what is currently five tools into one |
| 9. Hand off to engineering for deployment | Multi-week back-and-forth; engineering re-implements feature code; QA cycle | NO HAND-OFF. Quant promotes the model in the registry UI, the audit log records the promotion, the serving role lazy-reloads. End-to-end in seconds. | **Highest** — this is the central value prop. Collapses weeks to seconds. |
| 10. Monitor in production | Custom dashboards; usually inadequate; oncall is reactive | Inference log built in; per-inference drill-down; alerting on rate / latency / error / drift | **High** — converts a hand-rolled afterthought into a platform default |
| 11. Receive LP ODD questionnaire | Scramble for evidence; write 14-page document; LP's questions reveal gaps | Share-screen the platform UI; LP asks "show me a specific inference from 18 months ago," it appears in 60 seconds; LP asks "what was your walk-forward methodology," the screen shows it | **Highest** — converts a multi-day fire drill into a 30-minute screen-share |

**Total assessment:** The platform is High-or-Highest value at 7 of 11 workflow steps, Medium at 2, Table-stakes at 1, None at 1. The big wins are concentrated at steps 1, 4, 7, 8, 9, 10, 11 — the points in the workflow where the *infrastructure*, not the *modelling*, is the bottleneck. This is the right pattern. We are an infrastructure product; the quant's modelling craft is theirs.

The honest acknowledgement: we are NOT a model-research accelerator. A quant who already has a great Transformer architecture does not become a better quant by using our platform. A quant who has a great architecture and currently spends 60% of their time fighting infrastructure becomes 2.5x more productive on alpha research because we eliminate the infrastructure tax.

## 7. Pricing and segment

### 7.1 Pricing assumption

Annual contract, all-in, per tenant:

- **Starter tier** — $150-200k/year. Up to 3 strategies, up to 5 quant users, single tenant in vendor-managed GCP, standard support. Targets $500M-$1.5B AUM funds.
- **Professional tier** — $300-400k/year. Up to 10 strategies, up to 15 quant users, single tenant in vendor-managed GCP, priority support, monthly platform-engineer office hours. Targets $1.5B-$5B AUM funds.
- **Enterprise tier** — $500-800k/year + setup. Unlimited strategies, BYOC deployment in customer GCP, dedicated platform-engineering hours, custom integration. Targets $5B+ AUM funds; sales-qualified entry only.

These numbers are **provisional** and informed by the published anchors of comparable vendors (SigTech is rumoured to start in the $200-300k range and exceed $1M for enterprise; Domino is in the $100-300k range; Palantir Foundry is $1M+ minimum). They should be tested in actual sales conversations and revised after the first three pilots.

### 7.2 Segment focus for first 18 months

- **Primary:** mid-market hedge funds, $500M-$5B AUM, 20-80 staff, Western markets (US/UK/EU). The Professional tier customer.
- **Beachhead:** the user's existing relationships (Jenny Lin's network for warm intros, Morgan Stanley contact, future intros from these). 3-5 paid pilots in the first 12 months.
- **Expansion:** asset managers and quant arms of larger institutions in months 12-24, layered on top of the hedge-fund customer base.
- **Geography:** US (NYC, Chicago, Boston, SF) and UK (London) for the first 24 months. EU and APAC with localised regulatory expertise in years 3+.

### 7.3 Why this pricing

- **Below SigTech and Palantir** — those vendors target the enterprise tier; we are deliberately one tier down.
- **Above Domino's lowest tier** — because we offer quant-specific value Domino does not, and the customer should pay for that specificity.
- **Above the line where build-your-own becomes attractive** — pricing too low signals "you should just build it yourselves."
- **Below the line where Procurement requires CFO sign-off and a six-month sales cycle** — at $200-400k, a head of quant tech often has signing authority or needs only one approval; above $500k, the procurement process expands meaningfully.

## 8. Risks to the positioning

The positioning above is not bulletproof. The risks worth naming:

**P-1 — SigTech ships silo / BYOC.** If SigTech adds silo tenancy as a deployment option, our most concrete differentiator weakens. **Mitigation:** the open-source stack and the mid-market price point remain. But our "silo + BYOC" line stops being unique.

**P-2 — A SigTech customer reference contradicts our "they're proprietary" story.** If SigTech open-sources material parts of their stack in 2026-2027, the open-source-first differentiator weakens. **Mitigation:** monitor SigTech announcements; if this happens, double down on the silo and quant-native defaults.

**P-3 — Domino acquires a quant-specific add-on company.** A Domino + a quant-MLOps-specialist acquisition could close our quant-native gap. **Mitigation:** the silo and open-source differentiators remain; quant-native first-mover advantage compounds (we have López de Prado's measures correctly implemented and validated; an acquired add-on takes time to integrate well).

**P-4 — A new generic MLOps competitor adopts our differentiators.** The category is hot; copycats are likely. **Mitigation:** none specific to positioning; the answer is to compound the lead through customer success, product depth, and reference customers before the copycats reach feature parity.

**P-5 — The "we built it ourselves" customer wins because their build is good enough.** If 1-2 prominent target customers complete in-house builds and publicise the success, the build-vs-buy maths shifts against us in subsequent sales conversations. **Mitigation:** focus on customers whose engineering capacity is already constrained; do not fight customers who have decided to build; offer those customers components of our open-source stack as a wedge.

**P-6 — Jenny Lin's platform launches and is positioned identically.** Memory notes Jenny is building a peer/competitor product. If her positioning matches ours one-to-one, we have a zero-sum competition for the same niche. **Mitigation:** maintain warm relationship; sharpen our differentiation along axes she may not be choosing (e.g., open-source-first if she is proprietary; specific architectural choices like Postgres-centric); be prepared for either competition or partnership.

**P-7 — The market shifts toward enterprise consolidation.** If the next 24 months see large hedge funds acquiring smaller ones, the mid-market segment shrinks. **Mitigation:** the segment focus tilts toward asset managers and quant-curious institutional allocators in years 2-3.

**P-8 — Generative AI obsoletes the quant-native modelling craft.** If 2027-2028 sees LLM-driven alpha generation become the dominant paradigm, the value of "we make your quant team faster at traditional modelling" weakens. **Mitigation:** the platform's LLM signal-mining scaffolding (PRD T6.1-T6.4) is the answer; the platform should remain useful as a *productionalization layer* even when the upstream modelling craft shifts.

## 9. What this positioning means for every other artefact

Every customer-facing artefact (marketing site, demo, NotebookLM video, sales conversation, pitch deck) should be tested against this document. The test:

1. Does it lead with the one-sentence pitch (or a recognisable variant)?
2. Does it name the buyer, not just "hedge funds" generically?
3. Does it surface the three differentiators (silo + BYOC, open-source-first, quant-native)?
4. Does it anti-position against at least one of SigTech / Domino / Palantir / Databricks / build-your-own where relevant?
5. Does it avoid leading with engineering choices (CQRS, Postgres-centric, single-image-multi-role) as customer value?

If an artefact fails one of these, revise. If an artefact fails two or more, restart.

For the blueprint specifically:
- **Chapter 2 (Key Ideas)** should be rewritten to lead each architectural bet with its customer-value framing, not its engineering-choice framing. (Done in this commit.)
- **Chapter 3 (Design Brief)** Goal #1 should be re-scoped to make the dev-workflow vs. training-compute distinction explicit. (Done in this commit.)
- **A new Chapter 14.5 (Comparison to Alternatives)** should sit between Security and Roadmap. (Done in this commit.)

For the PRD specifically:
- **§1.1 (Current Situation)** should explicitly name SigTech as the primary competitor and reference this document. (Done in this commit.)

For the NotebookLM video (next phase):
- The customize-prompt directive must lead with the one-sentence pitch and require NotebookLM to anti-position against SigTech and Domino by name in the audio narrative.

---

*End of positioning document.*
