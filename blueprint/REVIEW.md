# Review Agent Instructions

This document briefs an agent tasked with reviewing the Quant Platform Blueprint for quality. The review is intended to run before the document is shared with external readers (the friend at Morgan Stanley; Jenny Lin; any prospective customer). Its purpose is to catch unfounded claims, missing citations, internal contradictions, and logical gaps while the document is still easy to fix.

## Scope

The review examines the blueprint source in `blueprint/src/*.md` and the rendered PDF at `blueprint/output/blueprint.pdf`. The source is canonical; the PDF is a derived artefact. Issues are reported against the source files with line numbers where possible.

The review does NOT re-decide architectural choices. If the document says "we choose FastAPI," the review does not argue the merits of Litestar; it verifies that the justification given is accurate and internally consistent. Architectural second-guessing is a separate activity.

## Reading protocol

Before issuing findings, the reviewer must read every file in `src/` in the order of the filename prefix (01, 02, 03, ...). This order reflects the document's intended narrative flow. Findings that report internal contradictions must cite at least two locations in the source.

## Checks to perform

The review runs five distinct checks. Each check produces a list of findings or an empty list if the check passes. The reviewer is not required to find something in every check; empty findings are valuable signals of document quality.

### Check 1: Unfounded claims

A claim is **unfounded** if it asserts a fact about the external world (market size, library performance, industry prevalence, regulatory requirement) without either a cited source or being a direct extrapolation from an assertion elsewhere in the document that is itself supported. Examples of claims to inspect:

- "Quant strategies are the favoured hedge-fund allocation heading into 2026"
- "PGMQ handles tens of thousands of messages per second"
- "uv is 10–100× faster than pip/poetry"
- "Half of hedge funds now offer separately managed accounts"
- "The single most common cause of backtest failure is look-ahead bias"

For each such claim the reviewer identifies:

1. The claim itself (exact quote)
2. The source file and line number
3. Whether a citation is present nearby
4. Whether the claim is load-bearing (does the architecture depend on it being true?) or decorative
5. A proposed action: add a citation, soften the language (e.g. "commonly cited as" instead of "the single most common"), or remove

Claims that are opinions (e.g. "less is more," "this trade is worth it") are not unfounded; they are editorial. They are flagged only if the surrounding language presents them as empirical.

### Check 2: Missing source attributions

Where the document makes a factual claim and a citation would strengthen it, the reviewer proposes a specific, authoritative source. Acceptable sources fall into three classes:

- **Peer-reviewed or industry-standard literature** — academic papers, well-known textbooks, established industry reports (Gartner, Forrester, With Intelligence, Barclays Prime)
- **Authoritative primary documentation** — library documentation, vendor documentation (GCP docs, Astral docs for uv/ruff, HashiCorp docs for Terraform, MLflow docs)
- **Reputable technical publications** — canonical blog posts from the library authors, conference talks with published slides, published case studies from the named organisation

Unacceptable sources include: anonymous blog posts, Medium articles without author credentials, AI-generated content farms, and opinion pieces presented as research.

The reviewer should not invent sources. If a credible source cannot be identified, the reviewer recommends softening or removing the claim.

### Check 3: Internal consistency

The reviewer verifies that the document does not contradict itself. Specific pairs to check:

- **Tenancy model.** The executive summary, design brief, infrastructure chapter, and security chapter must all describe silo tenancy consistently. Any surviving reference to pool tenancy, multi-tenant middleware, or row-level security should be flagged.
- **Technology stack.** The architecture chapter's tech-stack table is the canonical reference. Other chapters that mention technologies must be consistent with it. A chapter that mentions "pandas" when the table specifies "Polars" is a finding.
- **Deployment model.** Cloud Run vs Cloud Functions, Vertex AI vs Cloud Run Jobs, Cloud SQL vs AlloyDB, Terraform vs manual provisioning — every such choice should be stated once and referenced consistently.
- **Authentication flow.** The auth chapter describes the OIDC-to-session-JWT flow. Other chapters that touch authentication (observability, security, API) must not contradict this flow or introduce a different one.
- **File-based ingestion.** The data platform chapter describes four inbound patterns. Other chapters that reference ingestion must use these four patterns as the vocabulary, not introduce new ones.
- **Event flow and CQRS.** The application chapter describes the single-transaction CQRS path. Any other chapter mentioning event publishing, queueing, or projector behaviour must be consistent with that description.
- **Roadmap phases.** The roadmap defines phases with prerequisites. Any chapter that references "we will add X in phase N" must match the roadmap's actual phase definitions.

### Check 4: Logical consistency

The reviewer examines the document's reasoning for gaps. A logical gap exists when a conclusion does not follow from the premises given, or when a stated premise is itself unsupported.

Specific patterns to inspect:

- **Motivated trade-offs.** Every rejection of an alternative ("Litestar is considered but rejected because...") should give a reason that is internally coherent and grounded in the target context. "Because ecosystem maturity outweighs raw throughput" is defensible; "because it's newer" is not.
- **Claim-to-architecture alignment.** If the document asserts that "customers will demand BYOC," then the architecture chapter must provide BYOC. If the document asserts that "regulators require immutable audit trails," then the security chapter must describe immutable audit trails.
- **Acceptance conditions.** Each roadmap phase has an acceptance condition. The scope listed for that phase must be sufficient to achieve the acceptance condition, and must not depend on capabilities that a later phase introduces.
- **Preconditions.** Features described as depending on other features must list the dependencies accurately. A chapter that introduces capability X while assuming Y must cite where Y is established.

### Check 5: Hedging and over-confidence

The reviewer flags two failure modes:

- **Over-confidence.** Assertions stated as universal truth when they are context-dependent. "Polars is always faster than pandas" is over-confident; "Polars is faster than pandas at the workloads typical of this platform" is accurate. Flag and propose softer wording.
- **Excessive hedging.** Architectural positions qualified to the point of being non-committal. A document that hedges every recommendation is not useful as a blueprint. Flag sentences that hedge a claim the document's overall stance is actually confident about.

## Output format

The reviewer produces a single markdown file, `REVIEW_FINDINGS.md`, structured as:

```markdown
# Blueprint Review Findings

## Summary

{Two-sentence summary: how many findings in each check, overall quality assessment.}

## Check 1: Unfounded claims

### Finding 1.1
- **File**: `src/01-executive-summary.md`, line 12
- **Quote**: "{exact text}"
- **Issue**: {why this is a problem}
- **Load-bearing**: yes/no
- **Proposed action**: {add citation from X / soften to Y / remove}

### Finding 1.2
...

## Check 2: Missing source attributions

### Finding 2.1
- **Location**: `src/XX.md`, line Y
- **Claim**: "{text}"
- **Proposed source**: {specific citation}
- **Rationale**: {why this source is appropriate}

...

## Check 3: Internal consistency

### Finding 3.1
- **Locations**: `src/AA.md` line X and `src/BB.md` line Y
- **Contradiction**: {summary}
- **Proposed resolution**: {which statement to keep; what to change in the other}

...

## Check 4: Logical consistency

### Finding 4.1
- **Location**: `src/XX.md` line Y
- **Issue**: {description of the gap}
- **Proposed fix**: {what additional premise, citation, or argument is needed}

...

## Check 5: Hedging and over-confidence

### Finding 5.1
- **Location**: `src/XX.md` line Y
- **Category**: over-confidence / excessive hedging
- **Current text**: "{exact quote}"
- **Proposed text**: "{revised text}"

...

## Non-findings

{Things the reviewer inspected and found acceptable, noted briefly so the author knows the check was performed.}
```

## Review discipline

- Each finding must include a file path and a location within the file. Findings without locations are rejected.
- Each finding must include a proposed action. "This is wrong" without a proposed fix is rejected.
- Findings that depend on information outside the document (e.g. "the author's own research conversations") are out of scope; the review examines the document as written.
- The reviewer does not add opinions about whether an architectural choice is correct. Only about whether the argument the document makes for the choice is complete and coherent.
- If a check produces no findings, the reviewer explicitly states this in the output rather than omitting the section.

## Known acceptable positions

The following positions are design choices of the document and are out of scope for the review even if they could be argued against:

- Silo tenancy as the default
- Near-monolithic application shape
- Postgres-centric data plane
- Local-first development as non-negotiable
- GCP as the default cloud (with AWS acknowledged as a comparable choice)
- Python as the primary application language
- Cloud Run as the application runtime (not GKE)
- Absence of a calendar timeline in the roadmap

These are positions the document deliberately takes. The review verifies they are stated clearly and consistently, not whether they are correct.

## Completion criteria

The review is complete when `REVIEW_FINDINGS.md` exists with all five check sections populated (each either with findings or with an explicit "no findings" note), and the summary section provides a single-line quality verdict (e.g. "Ready to share," "Ready to share after addressing the three load-bearing findings," "Not ready; substantive revisions required").
