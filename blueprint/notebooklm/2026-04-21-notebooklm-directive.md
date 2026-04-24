---
title: NotebookLM Production Directive — Quant Platform v1
date: 2026-04-21
purpose: >
  Everything you need to produce the NotebookLM video and audio overviews for the
  Quant Platform v1: which sources to upload, the customize-prompt directive to paste,
  the chapter structure to aim for, the do-and-don't list, and the iteration plan.
audience: the operator (you) producing the NotebookLM collateral
---

# NotebookLM Production Directive — Quant Platform v1

## How to use this document

This document has two halves.

**Half 1 (sections 1-3) is the operator's how-to**: which sources to upload, in what tier order, and the customize-prompt directive to paste verbatim into NotebookLM. If you only read this, you can produce a credible video.

**Half 2 (sections 4-7) is the editorial reference**: tone notes, chapter targets, do-and-don't lists, iteration plan. Read this if NotebookLM's first output isn't quite right and you need to know what to tweak.

Time to first usable video, if everything goes smoothly: about 30 minutes (15 of NotebookLM generation, 15 of you tightening the directive after seeing the first cut).

## 1. Sources to upload

NotebookLM's free tier accepts up to 50 sources per notebook; paid is more. We do not need that many. The right set is **6 documents**, organised in three tiers. Upload Tier 1 first; only add Tier 2 and 3 if the first cut needs more substance.

### Tier 1 (essential — start here)

These four documents together carry the entire narrative. NotebookLM weights all sources roughly equally, so a tighter source set produces tighter narration.

1. **`blueprint/positioning/2026-04-21-positioning.md`** — the one-sentence pitch, buyer profile, three differentiators, head-to-heads with SigTech / Domino / Palantir / Databricks. This is the *load-bearing* source. If NotebookLM only had one document, this should be it.

2. **`blueprint/research/2026-04-21-modern-quant-synthesis.md`** — the 12,500-word domain synthesis (cross-sectional alpha, TS foundation models, LP-allocator framing). This gives NotebookLM the technical credibility to name-check López de Prado, Chronos, Moirai, AlphaGPT, iTransformer — names that signal domain literacy in the audio narration.

3. **`blueprint/prd/2026-04-21-quant-platform-v1.md`** — the 9,000-word v1 product spec including the 30-minute / 7-beat demo narrative. Gives NotebookLM the concrete "what the customer sees" hook for the visual portion of the video.

4. **`blueprint/src/14.5-comparison-to-alternatives.md`** — the explicit competitor head-to-head chapter. Ensures the narration anti-positions correctly rather than generically.

### Tier 2 (add if Tier 1 is not enough)

5. **`blueprint/src/02-key-ideas.md`** (the customer-value-first rewrite) — the architectural bets framed as customer outcomes. Gives NotebookLM more to draw on when asked to elaborate any specific architectural choice.

6. **`blueprint/output/blueprint.pdf`** — the rendered full blueprint (15 chapters + 14.5 + ToC, includes diagrams). Useful as a single bundled source if you want NotebookLM to have access to chapters not represented in Tier 1 (data platform, security, infrastructure). The downside of including it is that it duplicates content from Tier 1 and may dilute citation specificity. Default: include only if NotebookLM's first cut feels under-substantiated.

### Tier 3 (add when SDK artefacts are written; currently in progress)

7. **`blueprint/sdk/2026-04-21-quant-sdk-design.md`** — the SDK design spec being written by a parallel agent right now.

8. **`sdk/examples/csi300_alpha158_v1.py`** — the demo strategy file showing the SDK in use.

These are useful for a *technical-deep-dive variant* of the video aimed at quant-engineering leads (Morgan persona). For the LP-allocator-leaning video (Priya persona), they are not needed; the positioning + research synthesis are enough.

### Sources NOT to upload

Do not upload, even though they exist:
- `blueprint/REVIEW.md` and `blueprint/REVIEW_FINDINGS.md` — internal QA artefacts; would muddy the narration.
- `blueprint/src/04-environment-flavors.md`, `12-cicd-deployment.md`, `13-observability.md` — operational chapters; specific enough to derail the video into engineering minutiae.
- `docs/migration/from-qlib.md` (when written) — for a different audience (existing Qlib customers); irrelevant to the LP narrative.
- This file — it's the production directive, not source material.

## 2. The customize-prompt directive (paste verbatim)

In NotebookLM, when you click **Audio Overview** or **Video Overview** in the Studio panel, there is a **Customize** button. Paste the block below into that customize prompt. NotebookLM weights the customize prompt much more heavily than any individual source, so this is where the narration is steered.

The block is ~700 words; well within NotebookLM's customize-prompt budget.

---

```
AUDIENCE
Two audiences in parallel — speak to both. Primary: limited-partner allocators
(CIOs at pension funds, endowments, family offices) deciding which quantitative
hedge funds to allocate capital to. Secondary: the head of quant technology at
a mid-market hedge fund ($500M-$5B AUM) deciding whether to buy this platform
or build their own. Both are technically sophisticated. Speak as one technical
professional to another. Do not explain what an LP is, what a hedge fund is,
what backtesting is. Do explain what specific concepts mean (PBO, walk-forward,
bi-temporal data) the first time they appear.

ONE-SENTENCE THESIS — open the narration with this, paraphrased
"This is an open-source-first, silo-tenant productionalization platform that
lets a quant ship a model from notebook to audited production without an
engineering hand-off, and lets their fund pass an LP's operational due-diligence
questionnaire from screenshots in the UI."

THREE DIFFERENTIATORS — return to these throughout
1. Silo + BYOC tenancy: the customer's data and code stay in their cloud.
2. Open-source-first stack: portable, no vendor lock-in — including Dagster
   (open-source asset orchestration) as the pipeline layer.
3. Quant-native opinionated defaults: PBO, DSR, walk-forward, bi-temporal data,
   factor decomposition built in — not bolted on.

ANTI-POSITIONING — name competitors explicitly
- SigTech (London, Brevan Howard spinout): the closest direct competitor;
  proprietary, multi-tenant cloud, enterprise-priced. We are silo, open-source,
  mid-market priced.
- Domino Data Lab: generic enterprise MLOps, not quant-native.
- Palantir Foundry: enterprise consulting motion, not self-serve trial.
- Domino, Palantir Foundry: proprietary orchestration (Pipeline Builder,
  Foundry's pipeline graph). We use Dagster (open-source); the customer's
  asset definitions and run history live in their own Postgres.
- Databricks: data-platform-with-ML, overkill for the operational data volume of
  a $5B AUM hedge fund.
- Build-your-own: defensible at $20B+ AUM with 50+ engineers; bad math at the
  $500M-$5B segment we target.

DOMAIN CREDIBILITY — name-check these where natural
- López de Prado, Advances in Financial Machine Learning (Wiley 2018), and
  Bailey & López de Prado on the Probability of Backtest Overfitting (2014).
- Microsoft Qlib as the reference open-source quant platform.
- Time-series foundation models: Chronos (Amazon), Moirai (Salesforce),
  TimesFM (Google), TimeGPT (Nixtla), Lag-Llama.
- Man Group's AlphaGPT (LLM-generated alpha signals approved for live trading,
  publicly disclosed 2025).
- Cross-sectional alpha architectures: iTransformer, MASTER, PatchTST.
- Open-source orchestration: **Dagster** as the asset-graph layer; coexists
  with PGMQ for CQRS event flow.

NARRATIVE ARC — eight chapters, ~12 minutes
1. The one-sentence thesis + who buys this (1 min)
2. The actual quant workflow today and where the productionalization friction
   lives (2 min) — emphasize the multi-week research-to-production gap
3. The three differentiators in turn (2 min)
4. What credible 2026 quant looks like — modern alpha, foundation models,
   LLM-mining (2 min)
5. The platform — the seven-beat demo narrative compressed (2 min) — data
   provenance, research workspace, walk-forward, model promotion, audit, LP
   report
6. Where we fit vs SigTech, Domino, Palantir, Databricks (1 min)
7. What an LP allocator should ask their quant managers — five questions
   (1 min)
8. Closing: this is being built; the demo lands in 18 weeks (1 min)

TONE
Confident, technical, sober. This is a Bloomberg-terminal aesthetic, not a
TED talk. Match the register of a Risk.net long-read or a Hedgeweek interview.
Two-host conversation is fine for audio; the video should have a single
narrator with on-screen captions.

DO NOT SAY
- "Game-changing", "revolutionary", "next-generation", "AI-powered" —
  vapid AI-marketing register, immediate credibility loss.
- "State-of-the-art" or "SOTA" — overused; replace with specific named
  techniques.
- "Production runs on your laptop" — local-first means dev workflow on the
  laptop, training compute in the cloud. Do not oversell.
- "We use CQRS" or "we use Postgres" as if architectural choices were
  customer value. Translate: "your audit trail is queryable in the same
  database as your operational data" is the customer-facing version.
- Generic praise for any competitor — every mention should be specific
  about where they win and where we win.

LENGTH
Audio Overview: 15-20 minutes is the natural NotebookLM length; cap at 20.
Video Overview: target 10-12 minutes; do not exceed 15.
```

---

## 3. Generation steps

Once you've uploaded the Tier 1 sources and pasted the directive:

1. **Click Audio Overview → Generate.** Wait ~10 minutes. NotebookLM produces a 15-20 minute two-host conversation. Listen end to end. Note the moments where it (a) misses the thesis, (b) understates a differentiator, (c) is generic instead of specific. This is your first calibration.
2. **If the audio is good, generate Video Overview.** Same process, longer wait. The video uses NotebookLM's slide-based visualisation; the on-screen content comes from your sources, the narration is the same kind as the audio.
3. **Iterate the customize-prompt** if the first cut misses. Common edits: tighten the anti-positioning if NotebookLM is too soft on competitors; add a specific name-check if a section is too abstract; add a "do not say" line if a phrase keeps appearing.
4. **Add Tier 2 sources** if NotebookLM's narration feels under-substantiated. The PDF source is most useful when an architectural-choice question comes up that Tier 1 doesn't cover (e.g., "tell me about the security posture").
5. **Generate the technical-deep-dive variant** (separate notebook) once the SDK artefacts complete. Same Tier 1 sources plus the SDK design spec and the Qlib example file. Same directive but with chapters reweighted toward the SDK and the demo workload.

## 4. Tone reference (for editorial calibration)

When you're listening to NotebookLM's first cut and judging "is this the right register," compare against:

**Closer to right:**
- A Risk.net long-form analytical piece on a quant manager's strategy.
- A Hedgeweek interview with a fund's CTO.
- A Quantitative Brokers explainer video on optimal execution.
- A López de Prado talk at a CFA event.

**Wrong register:**
- A general-tech-podcast "tools for AI" episode.
- A startup pitch reel.
- A consulting firm's thought-leadership webinar.
- Anything that uses "leverage" as a verb in the SaaS sense.

If the first cut sounds closer to the wrong register, the most likely fix is tightening the "DO NOT SAY" list in the directive.

## 5. Chapter-by-chapter editorial notes

Each chapter from the directive's narrative arc, with the failure modes to watch for and the fixes.

**Chapter 1 — Thesis + buyer.** Failure mode: NotebookLM defaults to "this is a platform for hedge funds" instead of naming the buyer specifically. Fix: ensure the directive says "head of quant technology at a mid-market hedge fund, $500M-$5B AUM, 20-80 staff" — that level of specificity.

**Chapter 2 — Actual workflow + friction.** Failure mode: NotebookLM treats the workflow generically. Fix: in the directive, add "specifically describe the eleven workflow steps from `positioning §6`" — NotebookLM will pull the table.

**Chapter 3 — Three differentiators.** Failure mode: NotebookLM lists the differentiators but doesn't *defend* them. Fix: tell it to spend ~40 seconds on each, naming what the customer gets and what we sacrifice.

**Chapter 4 — Modern quant.** This is where NotebookLM is most likely to do well, since the research synthesis is dense and quotable. Failure mode: too much surface coverage, not enough depth. Fix: tell it to go deep on one modern architecture (iTransformer or Chronos) and one classical defender (GBDT) rather than skimming all of them.

**Chapter 5 — Platform.** Failure mode: chapter sounds like a feature checklist. Fix: tell it to walk the seven-beat demo narrative (PRD §3.3) as a *story*, not a list. When narrating the platform's data flow, NotebookLM should reference the Dagster asset graph as the customer-visible state-of-state — the lineage view that LP allocators ask for is built into Dagster's UI, not bolted on.

**Chapter 6 — Anti-positioning.** Failure mode: NotebookLM softens the comparisons (e.g., "SigTech is great too, we just chose differently"). Fix: tell it to use the specific "where they win, where we win" framing from `14.5-comparison-to-alternatives.md`.

**Chapter 7 — Five LP questions.** Failure mode: NotebookLM paraphrases generically. Fix: tell it to read the five questions from `research-synthesis §7.2` and use them verbatim or near-verbatim.

**Chapter 8 — Closing.** Failure mode: NotebookLM tries to be inspirational. Fix: tell it to keep this short (60 seconds), state the timeline (18 weeks to v1 demo), and end on a single question for the listener — "what would change in your conversation with your quant manager if they could show you this?"

## 6. Iteration plan

Realistic expectations: the first NotebookLM cut will be 70% right. The next two iterations get to 90%.

**Iteration 1 (first generation):**
- Upload Tier 1; paste directive verbatim; generate audio.
- Listen end to end; note timestamps where it misses.
- Common Iter 1 issues: too generic in chapter 1; understates anti-positioning in chapter 6; too long overall.

**Iteration 2:**
- Tighten the directive's anti-positioning section based on Iter 1 listen.
- Add 1-2 explicit "tell the audience X" lines if Iter 1 missed a key point.
- If Iter 1 was too long, add "cap each chapter at the times specified in the narrative arc."
- Regenerate audio. Should be 85%+ right.

**Iteration 3:**
- Final polish on the specific phrases NotebookLM keeps using that you don't want.
- Generate video at this point — the directive is now stable.

**When to stop iterating:** when the next iteration's deltas are stylistic preferences rather than substantive corrections. Three iterations is usually enough; more than five iterations is a sign the directive has gotten too long and self-contradictory.

## 7. After the video — distribution

Brief note since the user's stated goal is "kick off collateral production": the NotebookLM video is one piece of collateral, not the only one. Likely additional pieces, in order of priority:

1. **30-minute live demo** (the seven-beat PRD demo) — the artefact for actual sales conversations. Higher conversion than a video.
2. **The NotebookLM video itself** — for asynchronous prospect education; for warm intros where you can't be present.
3. **A short (60-90 second) cut of the video** — for embeds, social distribution, conference booth loops. Probably a separate NotebookLM generation with a tighter directive.
4. **One-page tear-sheet** — for inclusion in proposals, RFP responses. Drawn from positioning §1 (one-sentence pitch) + §4 (three differentiators) + §7 (pricing).
5. **Technical-deep-dive video variant** — for Morgan-persona prospects (heads of quant tech). Same NotebookLM, different source mix and directive.

The NotebookLM video is the *force multiplier* — once you have it, every other piece of collateral can reference or excerpt it. Get it 90% right; do not let perfect block shipping the 90% version.

---

## Appendix — quick checklist

Before clicking Generate the first time:

- [ ] Tier 1 sources (4 files) uploaded to NotebookLM
- [ ] Customize-prompt directive (Section 2) pasted verbatim into the customize box
- [ ] Audience setting: confirm it matches "general / unspecified" rather than NotebookLM's preset categories
- [ ] Length setting: NotebookLM 2026 lets you nudge length; aim for the 15-20 minute audio band
- [ ] Note your start time — track elapsed minutes for budget transparency

After the first generation:

- [ ] Listened end-to-end (do not skim)
- [ ] Noted three timestamps with substantive issues (not just stylistic)
- [ ] Decided whether to iterate the directive or accept Iter 1 as a baseline
- [ ] If iterating: edited the directive in Section 2 (commit your edits to git so the next NotebookLM session starts from your improved version)

When approving the final cut:

- [ ] One-sentence thesis stated clearly within the first 90 seconds
- [ ] All three differentiators named explicitly
- [ ] At least three of (SigTech, Domino, Palantir, Databricks, build-your-own) named with the specific where-they-win/where-we-win framing
- [ ] No phrases from the "DO NOT SAY" list survived
- [ ] Total length within the budget (audio ≤20 min, video ≤15 min)
