# RESUME — next session picks up here

> Read this file first when a new Claude Code session opens in this directory.
>
> This file should be deleted after M1 ships and its HIL signs off; it is kickoff-for-the-implementation-phase, not current-state documentation.

## Where we are

- **Branch:** `feat/m1-skeleton` (you are here if you see this file at repo root)
- **Main branch state:** MVP-B spec + M1 plan committed (commits: see `git log main`)
- **Previous session:** brainstorming → spec → plan, concluded 2026-04-23. MVP-A was parked 2026-04-22 after architectural retrospective.

## What to read, in this order

1. **Spec** — `docs/superpowers/specs/2026-04-23-quant-mvp-design.md`
   This is the full MVP design. 16 architecture decisions; 8 HIL-gated milestones; scope, out-of-scope, success criteria, risks.

2. **M1 plan** — `docs/superpowers/plans/2026-04-23-milestone-1-skeleton.md`
   14 tasks to build the skeleton. TDD throughout. Target: 2 workdays.

3. **Retrospective** — `docs/archive/LESSONS.md`
   Why we're not doing things the way MVP-A did them. Read before you deviate from the spec.

Optional reference:
- `docs/archive/START.md` — the prior session's kickoff brief
- `blueprint/` — reference architecture (broader than MVP; MVP is a narrower cut)
- `memory/` — user profile, feedback, reference pointers

## What to do

Invoke the **subagent-driven-development** skill:

```
Skill superpowers:subagent-driven-development
```

Then, per that skill's workflow:

1. Read `docs/superpowers/plans/2026-04-23-milestone-1-skeleton.md` once, extract all 14 tasks with full text + context into your working memory.
2. Create TaskCreate entries for each task.
3. For each task:
   - Dispatch an implementer subagent with the task's full text
   - Dispatch a spec-compliance reviewer subagent
   - Dispatch a code-quality reviewer subagent
   - Mark task complete
4. After all 14 tasks land on `feat/m1-skeleton`, run the M1 HIL checkpoint script at `docs/milestones/M1/hil.md` with the user.
5. Only after HIL signs off: merge `feat/m1-skeleton` → `main` and write the M2 plan.

## What NOT to do

- Do not start implementation on `main`. All M1 work lives on `feat/m1-skeleton`.
- Do not expand scope mid-build. MVP-A's failure mode. If HIL surfaces a gap, record it as a ticket (MUST-FIX / DEFER-TO-V2 / SPEC-UPDATE) per spec §11; do not silently grow M1.
- Do not skip HIL to save time. HIL gating is the spec's explicit mechanism for preventing MVP-A-style "23 tasks, 38 commits, no checkpoint" drift.
- Do not import Dagster. LESSONS.md §"The core mistake."

## Branch / commit hygiene

- One commit per task (14 commits for M1, per the plan).
- Commit message convention: `feat(M1-<task_number>): <short description>` — matches the plan's template.
- Do not merge to main before HIL approval.

## After M1 ships

Delete this file:
```bash
git rm RESUME.md && git commit -m "chore: remove RESUME.md (M1 shipped)"
```

Then write the M2 plan to `docs/superpowers/plans/2026-04-XX-milestone-2-validation-math.md` and repeat the cycle.
