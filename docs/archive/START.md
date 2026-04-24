# START — kickoff for the next planning session

> Read this file first when a new Claude Code session opens in this directory.

## Context

The previous attempt (MVP-A, 2026-04-21 → 2026-04-22) was built too fast without enough user feedback. It shipped 23 tasks, 38 commits, 114 passing tests — and the architecture was wrong. The work is parked on GitHub at `archive/mvp-a-rushed-2026-04-22` (tag: `archive-mvp-a-2026-04-22`) and locally at `../deployment/quant-platform-archive-2026-04/`. This repo has been reset to the pre-MVP-A baseline (`a9f902c`).

**Read [`LESSONS.md`](./LESSONS.md) before doing anything else.** It captures what went wrong, what worked, and the pre-Dagster architectural thinking that got steamrolled. The "Tech stack to re-evaluate" table at the bottom of LESSONS.md is the starting point for tech decisions in this session.

## Goal of this session

Define an **MVP** through brainstorming → spec → plan. Three pillars:

1. **SDK v0** — initial Python SDK that defines what a "strategy" is from the user's perspective. The SDK is the contract; the platform is the runtime. Previous SDK skeleton is at `../deployment/sdk/quantplatform/` (also bundled in `../deployment/quant-platform-archive-2026-04/`) for reference, but treat it as one input among many — not as a baseline to extend.

2. **Hello-world quant model** — pick the smallest credible quant workflow (single instrument, single signal, single backtest) and implement it end-to-end via the SDK. This is the demo: "look, you write 30 lines and you get a trained model + walk-forward report + promotion gate decision." The previous demo was synthetic OHLCV → Polars rolling features → LightGBM, which was honest but uninspiring; brainstorm a better hello-world.

3. **Clickable UI prototype** — not production frontend yet. Click-through screens that show the user-facing surface: log in, register a strategy, view runs, view a model card, see a walk-forward report. Static or stubbed data is fine. The point is to validate UX flows before committing to backend shapes. Reference UX stack is in `memory/reference_ux_patterns.md` (doodle-1 patterns).

## Tech stack re-evaluation

**Required:** the brainstorming session must produce an explicit decision on orchestration. The previous build's "add Dagster everywhere" was the worst architectural call (see LESSONS.md §"The core mistake"). The pre-Dagster baseline was PGMQ + APScheduler + worker, which supported every demoable behavior MVP-A produced. Default to that baseline; only adopt a heavier orchestrator if a specific MVP requirement justifies it.

**Document the reasoning either way.** If we choose PGMQ-only, write down why. If we choose Dagster (or anything else), write down what concrete property of the MVP requires it. Future sessions need to see the decision, not re-derive it.

## What I am NOT asking for in this session

- No implementation code yet.
- No test scaffolding yet.
- No 5,000-line plans.
- No subagent dispatch until we have a spec the user has signed off on.

The MVP-A failure mode was "execute first, evaluate after." Reverse it.

## How to start

1. Read [`LESSONS.md`](./LESSONS.md) end-to-end. Confirm with the user that the lessons match their understanding before brainstorming.
2. Use the **brainstorming** skill (`superpowers:brainstorming`). It will ask one question at a time, propose 2–3 approaches per decision point, and write a spec to `docs/superpowers/specs/YYYY-MM-DD-mvp-design.md`.
3. Cover the three pillars in sequence: SDK shape → hello-world model → UI prototype scope.
4. Re-evaluate tech stack as part of brainstorming, with the pre-Dagster baseline from LESSONS.md as the default.
5. After spec is approved by the user, invoke the **writing-plans** skill to produce an implementation plan.
6. **Stop and check in** with the user before any subagent execution begins.

## User context (carry-over)

- User goal: hedge-fund quant productionalization platform; peer-founder context with Jenny Lin (Morgan Stanley intro). Same silo-SaaS architecture class as LedgerTM.
- Golden rule: **everything runs locally via docker-compose**. No cloud-only services in the critical path. (`memory/feedback_architecture_monolith.md`)
- Python tooling: uv, ruff, pyright, Polars (lts-cpu on dev VM), Pydantic v2, FastAPI. (`memory/feedback_python_tooling.md`)
- Frontend reference: doodle-1 stack at `/Users/igormusic/code/doodle-1`. (`memory/reference_ux_patterns.md`)
- Dev/staging deploy: Windows Docker host at `192.168.2.250` (`ssh windows`), self-hosted GitHub Actions runner. (`memory/project_dev_deployment_target.md`)
- Auth pattern (battle-tested in MVP-A, keep): BFF + IdP federation, RS256 + JWKS, Postgres-backed sessions. (`memory/project_quant_platform_auth.md`)
- Writing style: don't use "SOTA" / "state-of-the-art" — those are instruction words for *you*, not for deliverables. (`memory/feedback_writing_style.md`)

## When this session ends

Move LESSONS.md and START.md into `docs/` (or wherever the spec ends up living). They are kickoff artifacts for *this one session*; they should not pollute the repo root long-term.
