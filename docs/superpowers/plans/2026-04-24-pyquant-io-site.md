# pyquant.io Marketing Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Note:** This is a content-site plan, not a TDD code plan. "Tests" are build verification + eyeball checks in a browser. Each task produces a commit; most commits are single-file or tight clusters.

**Goal:** Build and deploy a 6-page static Astro site for `pyquant.io`, reusing the design tokens from `/Users/igormusic/code/banking-demo`, sourced from `/Users/igormusic/code/quant-platform/blueprint/`, deployed via self-hosted GitHub Actions runner on `ubuntu-server.local`.

**Architecture:** Astro 5 static build + Tailwind v4 with `@theme` tokens mirrored from banking-demo → `dist/` → self-hosted runner rsyncs into `/srv/pyquant/site/` on ubuntu-server → served by existing Caddy (apex block switches from BFF reverse-proxy to `file_server`). Media files (video + podcast) live in `public/media/` on the server, not in git.

**Tech Stack:** Astro 5, Tailwind v4 (`@tailwindcss/vite`), pnpm, TypeScript, Prettier. No client-side JS frameworks. GitHub Actions (`ubuntu-latest` for CI, `self-hosted` for deploy). Caddy 2 + `caddy-dns/cloudflare` plugin (already installed on ubuntu-server).

**Spec:** `docs/SPEC.md` (copy of `quant-platform/docs/superpowers/specs/2026-04-24-pyquant-io-site-design.md`).

---

## File structure produced by this plan

```
pyquant-site/
├── README.md                                # Task 19
├── .gitignore                                # Task 1
├── .prettierrc.json                          # Task 4
├── astro.config.mjs                          # Task 2
├── package.json                              # Task 1
├── pnpm-lock.yaml                            # Task 1 (generated)
├── tsconfig.json                             # Task 1
├── docs/
│   ├── SPEC.md                               # (pre-populated — design spec)
│   └── start.md                              # (pre-populated — session kickoff)
├── public/
│   ├── favicon.svg                           # Task 3
│   └── media/                                # NOT in git — uploaded out-of-band (Task 16)
├── src/
│   ├── styles/
│   │   └── tokens.css                        # Task 2
│   ├── layouts/
│   │   └── Base.astro                        # Task 5
│   ├── components/
│   │   ├── Nav.astro                         # Task 5
│   │   ├── Footer.astro                      # Task 5
│   │   ├── DifferentiatorCard.astro          # Task 6
│   │   ├── WorkflowTable.astro               # Task 6
│   │   ├── ComparisonTable.astro             # Task 6
│   │   └── MediaEmbed.astro                  # Task 6
│   ├── data/
│   │   ├── nav.ts                            # Task 5
│   │   ├── differentiators.ts                # Task 6
│   │   ├── workflow.ts                       # Task 6
│   │   └── comparisons.ts                    # Task 6
│   └── pages/
│       ├── index.astro                       # Task 7
│       ├── product.astro                     # Task 8
│       ├── architecture.astro                # Task 9
│       ├── comparisons.astro                 # Task 10
│       ├── principles.astro                  # Task 11
│       └── media.astro                       # Task 12
└── .github/
    └── workflows/
        ├── ci.yml                            # Task 13
        └── deploy.yml                        # Task 14
```

Server-side (ubuntu-server):
- `/srv/pyquant/site/` — created in Task 15
- `/srv/pyquant/site/media/{video.mp4,podcast.m4a}` — uploaded in Task 16
- `quant-runner` container — bind mount + re-registered in Task 17
- `/srv/ledgertm/Caddyfile` — apex block edited in Task 18

---

## Phase 1 — Bootstrap (Tasks 1–4)

### Task 1: Initialize Astro + pnpm + TypeScript

**Files:**
- Create: `pyquant-site/package.json`, `pyquant-site/astro.config.mjs`, `pyquant-site/tsconfig.json`, `pyquant-site/.gitignore`

- [ ] **Step 1: Bootstrap Astro with pnpm**

From `~/code/pyquant-site/` (the repo already exists and is cloned):
```bash
cd ~/code/pyquant-site
pnpm create astro@latest . --template minimal --typescript strict --install --no-git --skip-houston --yes
```
Expected: `astro.config.mjs`, `package.json`, `tsconfig.json`, `src/pages/index.astro` created. pnpm installs dependencies. No prompts.

- [ ] **Step 2: Verify the default build works**

```bash
pnpm run build
```
Expected: `dist/index.html` created, exit 0. Contains "Welcome to Astro".

- [ ] **Step 3: Replace the default `.gitignore` with a stricter one**

Overwrite `.gitignore`:
```gitignore
# Dependencies
node_modules/

# Build output
dist/
.astro/

# Media (uploaded out of band to server, not in git — see SPEC.md §6)
public/media/

# Editor / OS
.DS_Store
.idea/
.vscode/*
!.vscode/extensions.json
*~
*.swp

# Env
.env
.env.*
!.env.example

# Logs
*.log
pnpm-debug.log*
```

- [ ] **Step 4: Commit**

```bash
cd ~/code/pyquant-site
git add .
git commit -m "chore: bootstrap Astro + pnpm scaffold"
```

**Checkpoint:** `pnpm run build` succeeds. `git log --oneline` shows one commit.

---

### Task 2: Add Tailwind v4 + design tokens from banking-demo

**Files:**
- Modify: `pyquant-site/astro.config.mjs`, `pyquant-site/package.json`
- Create: `pyquant-site/src/styles/tokens.css`

- [ ] **Step 1: Install Tailwind v4 for Astro**

```bash
cd ~/code/pyquant-site
pnpm add -D tailwindcss @tailwindcss/vite
```
Expected: `tailwindcss` and `@tailwindcss/vite` appear under `devDependencies` in `package.json`.

- [ ] **Step 2: Wire Tailwind into Astro's Vite config**

Overwrite `astro.config.mjs`:
```js
// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://pyquant.io',
  output: 'static',
  build: {
    format: 'directory',
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
```

- [ ] **Step 3: Create the tokens file (mirrors banking-demo's @theme block exactly)**

Create `src/styles/tokens.css`:
```css
@import "tailwindcss";

@theme {
  --color-background: #ffffff;
  --color-foreground: #0a0a0a;
  --color-card: #ffffff;
  --color-card-foreground: #0a0a0a;
  --color-popover: #ffffff;
  --color-popover-foreground: #0a0a0a;
  --color-primary: #1a365d;
  --color-primary-foreground: #f8fafc;
  --color-secondary: #f1f5f9;
  --color-secondary-foreground: #1e293b;
  --color-muted: #f1f5f9;
  --color-muted-foreground: #64748b;
  --color-accent: #f1f5f9;
  --color-accent-foreground: #1e293b;
  --color-destructive: #ef4444;
  --color-destructive-foreground: #ffffff;
  --color-border: #e2e8f0;
  --color-input: #e2e8f0;
  --color-ring: #1a365d;
  --color-success: #16a34a;
  --color-warning: #f59e0b;
  --radius-sm: 0.25rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-xl: 0.75rem;
}

* {
  border-color: var(--color-border);
}

body {
  margin: 0;
  background-color: #f8fafc;
  color: var(--color-foreground);
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
}
```

Note: `background-color: #f8fafc` matches banking-demo's subtle off-white (slate-50), not pure white.

- [ ] **Step 4: Verify build still passes**

```bash
pnpm run build
```
Expected: exit 0. Tailwind classes won't yet appear anywhere; we're just verifying the plumbing.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: add Tailwind v4 + banking-demo design tokens"
```

**Checkpoint:** `cat src/styles/tokens.css | grep 1a365d` returns the primary-color line.

---

### Task 3: Add favicon + minimal public assets

**Files:**
- Create: `pyquant-site/public/favicon.svg`

- [ ] **Step 1: Replace Astro's default favicon with a simple wordmark**

Overwrite `public/favicon.svg`:
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="8" fill="#1a365d"/>
  <text x="32" y="42" text-anchor="middle" fill="#f8fafc"
        font-family="Inter, system-ui, sans-serif" font-weight="700" font-size="28">pq</text>
</svg>
```

- [ ] **Step 2: Commit**

```bash
git add public/favicon.svg
git commit -m "feat: navy-on-white pq wordmark favicon"
```

---

### Task 4: Add Prettier + a build sanity script

**Files:**
- Create: `pyquant-site/.prettierrc.json`
- Modify: `pyquant-site/package.json`

- [ ] **Step 1: Install Prettier**

```bash
cd ~/code/pyquant-site
pnpm add -D prettier prettier-plugin-astro
```

- [ ] **Step 2: Create `.prettierrc.json`**

```json
{
  "plugins": ["prettier-plugin-astro"],
  "singleQuote": true,
  "semi": true,
  "tabWidth": 2,
  "printWidth": 100,
  "trailingComma": "all",
  "overrides": [
    { "files": "*.astro", "options": { "parser": "astro" } }
  ]
}
```

- [ ] **Step 3: Add `lint` and `format` scripts to `package.json`**

Edit `package.json` — add to the `"scripts"` object:
```json
"lint": "astro check && prettier --check 'src/**/*.{astro,ts,tsx,js,mjs,css}'",
"format": "prettier --write 'src/**/*.{astro,ts,tsx,js,mjs,css}'"
```

- [ ] **Step 4: Run format once to normalize**

```bash
pnpm run format
pnpm run lint
```
Expected: `astro check` reports 0 errors; prettier reports all files formatted.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "chore: prettier + astro check with lint/format scripts"
```

**Checkpoint:** `pnpm run lint` exits 0.

---

## Phase 2 — Layout and shared components (Tasks 5–6)

### Task 5: Base layout, Nav, Footer

**Files:**
- Create: `pyquant-site/src/layouts/Base.astro`, `pyquant-site/src/components/Nav.astro`, `pyquant-site/src/components/Footer.astro`, `pyquant-site/src/data/nav.ts`

- [ ] **Step 1: Create `src/data/nav.ts`**

```ts
export type NavItem = { href: string; label: string };

export const navItems: NavItem[] = [
  { href: '/', label: 'Home' },
  { href: '/product/', label: 'Product' },
  { href: '/architecture/', label: 'Architecture' },
  { href: '/comparisons/', label: 'Comparisons' },
  { href: '/principles/', label: 'Principles' },
  { href: '/media/', label: 'Media' },
];

export const contactEmail = 'freesidenomad@gmail.com';
```

- [ ] **Step 2: Create `src/components/Nav.astro`**

```astro
---
import { navItems } from '../data/nav';
const { pathname } = Astro.url;
const isActive = (href: string) =>
  href === '/' ? pathname === '/' : pathname.startsWith(href);
---

<nav class="border-b border-gray-100 bg-white">
  <div class="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
    <a href="/" class="flex items-center gap-2 text-[#1a365d]">
      <span class="inline-flex h-7 w-7 items-center justify-center rounded-md bg-[#1a365d] text-xs font-bold text-[#f8fafc]">pq</span>
      <span class="text-sm font-semibold tracking-tight">pyquant.io</span>
    </a>
    <ul class="flex items-center gap-6">
      {navItems.slice(1).map((item) => (
        <li>
          <a
            href={item.href}
            class:list={[
              'text-sm transition',
              isActive(item.href)
                ? 'font-semibold text-[#1a365d] border-b-2 border-[#1a365d] pb-1'
                : 'text-gray-600 hover:text-[#1a365d]',
            ]}
          >
            {item.label}
          </a>
        </li>
      ))}
    </ul>
  </div>
</nav>
```

- [ ] **Step 3: Create `src/components/Footer.astro`**

```astro
---
import { contactEmail } from '../data/nav';
const year = new Date().getFullYear();
---

<footer class="mt-24 border-t border-gray-100 bg-white">
  <div class="mx-auto max-w-5xl px-6 py-8 text-xs text-gray-500">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <p>&copy; {year} pyquant.io — pre-v1.</p>
      <a href={`mailto:${contactEmail}`} class="text-gray-700 underline-offset-2 hover:text-[#1a365d] hover:underline">
        Email us
      </a>
    </div>
  </div>
</footer>
```

- [ ] **Step 4: Create `src/layouts/Base.astro`**

```astro
---
import '../styles/tokens.css';
import Nav from '../components/Nav.astro';
import Footer from '../components/Footer.astro';

interface Props {
  title: string;
  description: string;
}

const { title, description } = Astro.props;
const canonicalUrl = new URL(Astro.url.pathname, Astro.site);
---

<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="generator" content={Astro.generator} />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="canonical" href={canonicalUrl} />
    <title>{title} — pyquant.io</title>
    <meta name="description" content={description} />
    <meta property="og:title" content={`${title} — pyquant.io`} />
    <meta property="og:description" content={description} />
    <meta property="og:url" content={canonicalUrl} />
    <meta property="og:type" content="website" />
    <meta name="robots" content="index, follow" />
  </head>
  <body>
    <Nav />
    <main class="mx-auto max-w-5xl px-6 py-12">
      <slot />
    </main>
    <Footer />
  </body>
</html>
```

- [ ] **Step 5: Update `src/pages/index.astro` to smoke-test the layout**

Overwrite `src/pages/index.astro`:
```astro
---
import Base from '../layouts/Base.astro';
---

<Base
  title="pyquant.io"
  description="Silo-tenant, open-source-first, quant-native productionalization platform for mid-market systematic hedge funds."
>
  <p class="text-sm text-gray-600">Scaffolding works. Real content lands in Task 7.</p>
</Base>
```

- [ ] **Step 6: Build and preview**

```bash
pnpm run build
pnpm run preview
```
Expected: a URL prints (usually `http://localhost:4321/`). Open in a browser; verify: nav renders six links; clicking a link 404s (that's fine — pages come next); footer shows year + Email us link; Inter font is used (or system fallback).

Kill preview with Ctrl+C.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: base layout, nav, footer"
```

**Checkpoint:** `pnpm run lint` clean; preview renders nav + footer; primary color visible.

---

### Task 6: Reusable content components + data files

**Files:**
- Create: `pyquant-site/src/components/DifferentiatorCard.astro`, `pyquant-site/src/components/WorkflowTable.astro`, `pyquant-site/src/components/ComparisonTable.astro`, `pyquant-site/src/components/MediaEmbed.astro`
- Create: `pyquant-site/src/data/differentiators.ts`, `pyquant-site/src/data/workflow.ts`, `pyquant-site/src/data/comparisons.ts`

- [ ] **Step 1: Create `src/data/differentiators.ts`**

Content derived from `blueprint/positioning/2026-04-21-positioning.md §4`. The *wording* is a slight compression; if the positioning doc evolves, re-derive.

```ts
export type Differentiator = {
  slug: string;
  headline: string;
  oneLiner: string;
  body: string;
};

export const differentiators: Differentiator[] = [
  {
    slug: 'silo-byoc',
    headline: 'Silo + BYOC by default',
    oneLiner: 'Your data and code stay in your cloud.',
    body:
      'Every tenant runs in a dedicated GCP project — optionally in your own GCP organisation. No shared database, no shared application process, no shared secrets vault. LP operational due-diligence questions about residency and isolation answer themselves.',
  },
  {
    slug: 'open-source',
    headline: 'Open-source-first stack',
    oneLiner: 'No vendor lock-in — you can self-host if you choose.',
    body:
      'Polars, Postgres + extensions, MLflow, Dagster, FastAPI, React, Vite, uv, Cloud Run. Every load-bearing component is permissively licensed. A fund that wants to pull infrastructure in-house in three years can do so without a re-platforming exercise.',
  },
  {
    slug: 'quant-native',
    headline: 'Quant-native, not generic MLOps',
    oneLiner: 'Walk-forward, PBO, DSR, bi-temporal data as defaults — not add-ons.',
    body:
      'PBO/DSR computed on every backtest. Walk-forward validation gates model promotion. CPCV instead of vanilla k-fold. _knowable_at filtering at query-build time, not researcher discretion. A prospect can tell in 90 seconds whether the platform was built by people who know the field.',
  },
];
```

- [ ] **Step 2: Create `src/components/DifferentiatorCard.astro`**

```astro
---
import type { Differentiator } from '../data/differentiators';
interface Props { d: Differentiator }
const { d } = Astro.props;
---

<article id={d.slug} class="rounded-lg border border-gray-100 bg-white p-6 shadow-sm transition hover:shadow-md">
  <h3 class="text-base font-semibold text-[#1a365d]">{d.headline}</h3>
  <p class="mt-1 text-xs font-medium uppercase tracking-wide text-gray-500">{d.oneLiner}</p>
  <p class="mt-4 text-sm leading-relaxed text-gray-700">{d.body}</p>
</article>
```

- [ ] **Step 3: Create `src/data/workflow.ts`**

Derived from `blueprint/positioning/2026-04-21-positioning.md §6` (11-step table). Preserve the value-level labels ("High" / "Highest" / "Medium" / "None") — they're part of the honest framing.

```ts
export type WorkflowStep = {
  n: number;
  today: string;
  platform: string;
  value: 'None' | 'Table-stakes' | 'Medium' | 'High' | 'Highest';
};

export const workflow: WorkflowStep[] = [
  { n: 1,  today: 'Open laptop, set up environment. Fight with conda/pip/poetry; Docker for some deps; hours-days.',
           platform: 'One `make demo-fresh` command. Full local stack — Postgres, MinIO, mock OIDC, MLflow — in 5 minutes.', value: 'High' },
  { n: 2,  today: 'Connect to data. Per-source auth; per-source schema discovery.',
           platform: 'Data is already typed, validated, point-in-time correct in the gold layer. Polars dataframe is a function call.', value: 'High' },
  { n: 3,  today: 'Sample for exploration — pandas + ad-hoc SQL.',
           platform: 'Polars lazy; one query API across silver and gold.', value: 'Medium' },
  { n: 4,  today: 'Iterate feature code in notebook. Copy-paste between research and production; functions slowly diverge.',
           platform: 'The notebook imports the same `features/` module the production serving path uses. One source of truth.', value: 'High' },
  { n: 5,  today: 'Test feature on sample. Visual inspection; ad-hoc unit tests.',
           platform: 'Pandera schema validation runs automatically. Integration tests against the local docker-compose stack.', value: 'Medium' },
  { n: 6,  today: 'Commit to git.',
           platform: 'Commit to git (no platform addition).', value: 'Table-stakes' },
  { n: 7,  today: 'Kick off real training. Slurm / SageMaker / internal k8s; wait hours.',
           platform: 'One-click submission to Cloud Run Jobs (CPU) or Vertex AI (GPU). Each fold materialised as a Dagster asset; MLflow records the run.', value: 'High' },
  { n: 8,  today: 'Review trained model across MLflow + internal dashboards + SHAP plots in another notebook.',
           platform: 'Run-detail UI shows metrics, walk-forward evidence, PBO/DSR, factor attribution, baseline comparison — one screen. Visual lineage from bronze to model version.', value: 'High' },
  { n: 9,  today: 'Hand off to engineering for deployment. Multi-week back-and-forth; re-implementation; QA cycle.',
           platform: 'NO HAND-OFF. Quant promotes in the registry UI; audit log records it; serving lazy-reloads. End-to-end in seconds.', value: 'Highest' },
  { n: 10, today: 'Monitor in production — custom dashboards, usually inadequate; oncall is reactive.',
           platform: 'Inference log built in. Per-inference drill-down. Alerts on rate / latency / error / drift.', value: 'High' },
  { n: 11, today: 'Receive LP ODD questionnaire — scramble for evidence; 14-page doc; LP questions reveal gaps.',
           platform: 'Share-screen the UI. LP asks "show me a specific inference 18 months ago" — appears in 60 seconds. LP asks "what was your walk-forward methodology" — the screen shows it.', value: 'Highest' },
];
```

- [ ] **Step 4: Create `src/components/WorkflowTable.astro`**

```astro
---
import { workflow } from '../data/workflow';

const valueColor = (v: string) =>
  ({
    Highest: 'bg-[#16a34a] text-white',
    High: 'bg-[#16a34a]/15 text-[#14532d]',
    Medium: 'bg-[#f59e0b]/15 text-[#78350f]',
    'Table-stakes': 'bg-gray-100 text-gray-600',
    None: 'bg-gray-50 text-gray-400',
  })[v] ?? 'bg-gray-100 text-gray-600';
---

<div class="overflow-x-auto">
  <table class="w-full border-collapse text-sm">
    <thead>
      <tr class="border-b border-gray-100 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
        <th class="px-3 py-2 w-10">#</th>
        <th class="px-3 py-2">Today</th>
        <th class="px-3 py-2">With pyquant.io</th>
        <th class="px-3 py-2 w-28">Value</th>
      </tr>
    </thead>
    <tbody>
      {workflow.map((s) => (
        <tr class="border-b border-gray-100 align-top">
          <td class="px-3 py-4 text-xs text-gray-400">{s.n}</td>
          <td class="px-3 py-4 text-gray-700">{s.today}</td>
          <td class="px-3 py-4 text-gray-900">{s.platform}</td>
          <td class="px-3 py-4">
            <span class:list={['inline-block rounded-md px-2 py-0.5 text-xs font-medium', valueColor(s.value)]}>
              {s.value}
            </span>
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

- [ ] **Step 5: Create `src/data/comparisons.ts`**

Derived from `blueprint/positioning/2026-04-21-positioning.md §5`. Include the five head-to-heads; preserve the "we punt" honesty.

```ts
export type Comparison = {
  name: string;
  theyWin: string;
  weWin: string;
  wePunt: string;
  salesLine: string;
};

export const comparisons: Comparison[] = [
  {
    name: 'SigTech',
    theyWin:
      'Six years of maturity, deep data curation, MAGIC AI agent layer, brand in London/Europe, integrations with existing vendors, polished enterprise sales motion.',
    weWin:
      'Silo + BYOC tenancy (data stays in your cloud, not theirs), open-source stack with portability, mid-market price point, transparent quant-native methodology documented in the UI rather than behind a sales call, local-first developer workflow.',
    wePunt:
      'Top-tier enterprise customers ($10B+ AUM) — SigTech is a better fit there; we do not contest that segment for v1.',
    salesLine:
      '"SigTech is the right answer for $10B+ AUM funds that want a managed enterprise quant platform. We are the right answer for $500M–$5B AUM funds that need quant-grade discipline but want to keep the data and code in their own cloud."',
  },
  {
    name: 'Domino Data Lab',
    theyWin:
      'Generic enterprise MLOps maturity, Fortune 100 deployment scale, non-Python tooling integration, forward-deployed-engineer customer-success motion.',
    weWin:
      'Quant-native opinionated defaults (Domino is generic MLOps you teach to do quant; we are quant-native out of the box), open-source stack vs. proprietary, silo + BYOC by default, lower price point.',
    wePunt:
      'Non-quant ML workloads — medical imaging, NLP for customer service, supply-chain optimisation. Domino is a better fit.',
    salesLine:
      '"Domino is the right answer if you have a generic data-science org with diverse ML workloads. We are the right answer if you are specifically a quant shop and you want PBO, walk-forward, bi-temporal data, and factor-decomposed reporting as defaults."',
  },
  {
    name: 'Palantir Foundry / AIP',
    theyWin:
      'Enterprise reach, multi-domain platform breadth, AIP agent layer, forward-deployed engineers, government/defence presence, Model Studio.',
    weWin:
      'Mid-market self-serve sales motion (no six-figure PS engagement to deploy), quant-native focus (Foundry is multi-domain; we are quant by design), open-source orchestration (Dagster) vs. proprietary pipeline runtime, transparent pricing.',
    wePunt:
      'Customers who already have Foundry, or who want a multi-domain enterprise platform spanning operations, supply chain, and analytics alongside quant.',
    salesLine:
      '"Foundry is the right answer for multi-domain enterprises with $5M+ platform budgets and a willingness to engage forward-deployed engineers. We are the right answer for hedge funds that want a focused product with a self-serve trial path."',
  },
  {
    name: 'Databricks',
    theyWin:
      'Data-engineering scale, Spark / Delta Lake ecosystem, MLflow ownership, Lakehouse architecture for petabyte-scale customers, broad enterprise sales motion.',
    weWin:
      'Right-sized for actual hedge-fund data volume (Postgres handles a $5B AUM fund trivially; Spark is overkill), quant-native defaults vs. generic ML, silo + BYOC vs. workspace model, opinionated rather than toolkit.',
    wePunt:
      'Petabyte-scale data lakes (alt-data heavy, satellite imagery, social firehose). Databricks wins that segment.',
    salesLine:
      '"Databricks is the right answer if your bottleneck is data scale and you need Spark. We are the right answer if your bottleneck is research-to-production friction and your operational data fits in Postgres — which is almost every quant shop under $20B AUM."',
  },
  {
    name: 'Build your own',
    theyWin:
      'Total control; no vendor to manage; no procurement; customised to your exact workflow; no recurring licence cost.',
    weWin:
      'Time-to-value (weeks vs. 18–30 months minimum), opportunity cost (your engineers work on alpha, not infrastructure), benchmark of best practices (López de Prado is already implemented and validated), upgrade compounding (every feature we add, you get without paying engineering for it).',
    wePunt:
      'Funds with $20B+ AUM and 50+ engineers — they have the capacity to build well; we do not target them.',
    salesLine:
      '"Building this yourself is reasonable if you are a $20B+ fund with 50+ engineers and a CTO with two years of patience. For a $500M–$5B fund with under 25 engineers, the maths does not work."',
  },
];
```

- [ ] **Step 6: Create `src/components/ComparisonTable.astro`**

```astro
---
import { comparisons } from '../data/comparisons';
---

<div class="space-y-8">
  {comparisons.map((c) => (
    <article class="rounded-lg border border-gray-100 bg-white p-6 shadow-sm">
      <h3 class="text-lg font-semibold text-[#1a365d]">vs {c.name}</h3>
      <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div>
          <p class="text-xs font-semibold uppercase tracking-wide text-gray-500">They win on</p>
          <p class="mt-1 text-sm text-gray-700">{c.theyWin}</p>
        </div>
        <div>
          <p class="text-xs font-semibold uppercase tracking-wide text-[#1a365d]">We win on</p>
          <p class="mt-1 text-sm text-gray-900">{c.weWin}</p>
        </div>
        <div>
          <p class="text-xs font-semibold uppercase tracking-wide text-gray-500">We punt on</p>
          <p class="mt-1 text-sm text-gray-700">{c.wePunt}</p>
        </div>
      </div>
      <blockquote class="mt-4 border-l-2 border-[#1a365d] pl-3 text-sm italic text-gray-700">
        {c.salesLine}
      </blockquote>
    </article>
  ))}
</div>
```

- [ ] **Step 7: Create `src/components/MediaEmbed.astro`**

```astro
---
interface Props {
  kind: 'video' | 'audio';
  src: string;
  title: string;
  description: string;
}
const { kind, src, title, description } = Astro.props;
---

<figure class="rounded-lg border border-gray-100 bg-white p-6 shadow-sm">
  <figcaption class="mb-4">
    <p class="text-base font-semibold text-[#1a365d]">{title}</p>
    <p class="mt-1 text-sm text-gray-600">{description}</p>
  </figcaption>
  {kind === 'video' ? (
    <video controls preload="metadata" class="w-full rounded-md border border-gray-100 bg-black">
      <source src={src} type="video/mp4" />
      Your browser does not support the video tag. <a href={src} class="underline">Download the MP4.</a>
    </video>
  ) : (
    <audio controls preload="metadata" class="w-full">
      <source src={src} type="audio/mp4" />
      Your browser does not support the audio tag. <a href={src} class="underline">Download the M4A.</a>
    </audio>
  )}
</figure>
```

- [ ] **Step 8: Verify build + lint**

```bash
pnpm run lint && pnpm run build
```
Expected: both exit 0.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: shared components + data files (differentiators, workflow, comparisons, media)"
```

**Checkpoint:** `ls src/components src/data` shows 4 components + 4 data files.

---

## Phase 3 — Pages (Tasks 7–12)

Each page imports `Base` and the components it needs. Keep copy derived from blueprint sources; preserve the honest framing (no marketing-speak, no name-dropping, no testimonials, no "start free trial").

### Task 7: Home (`/`)

**Files:**
- Modify: `pyquant-site/src/pages/index.astro`

- [ ] **Step 1: Overwrite `src/pages/index.astro`**

```astro
---
import Base from '../layouts/Base.astro';
import DifferentiatorCard from '../components/DifferentiatorCard.astro';
import { differentiators } from '../data/differentiators';
import { contactEmail } from '../data/nav';
---

<Base
  title="pyquant.io"
  description="Silo-tenant, open-source-first, quant-native productionalization platform for mid-market systematic hedge funds."
>
  <section class="max-w-3xl">
    <h1 class="text-2xl font-semibold text-[#1a365d]">
      An <span class="border-b-2 border-[#1a365d]">open-source-first, silo-tenant</span> productionalization platform for quant shops.
    </h1>
    <p class="mt-4 text-sm leading-relaxed text-gray-700">
      Ship a model from notebook to audited production without an engineering hand-off.
      Answer your next LP operational due-diligence questionnaire from screenshots in the UI.
      Run in our managed GCP — or in your own, with BYOC.
    </p>
    <p class="mt-4 text-sm text-gray-600">
      We are pre-v1. The architecture is in the
      <a href="/architecture/" class="underline-offset-2 hover:text-[#1a365d] hover:underline">Architecture</a> page;
      comparison to SigTech / Domino / Palantir / Databricks is on the
      <a href="/comparisons/" class="underline-offset-2 hover:text-[#1a365d] hover:underline">Comparisons</a> page.
    </p>
  </section>

  <section class="mt-16">
    <p class="text-xs font-semibold uppercase tracking-wide text-gray-500">Three load-bearing differentiators</p>
    <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
      {differentiators.map((d) => <DifferentiatorCard d={d} />)}
    </div>
  </section>

  <section class="mt-16 max-w-2xl">
    <p class="text-sm text-gray-700">
      Evaluating for a specific fund?
      <a href={`mailto:${contactEmail}`} class="font-medium underline-offset-2 hover:text-[#1a365d] hover:underline">Email us.</a>
    </p>
  </section>
</Base>
```

- [ ] **Step 2: Build + preview + eyeball**

```bash
pnpm run build && pnpm run preview
```
Open the printed URL. Verify: title under 30 seconds of scanning communicates "silo, open-source, quant"; no splashy hero; three differentiator cards are visually equal-weight; one accent underline, nothing else flashy.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat: home page"
```

---

### Task 8: Product (`/product/`)

**Files:**
- Create: `pyquant-site/src/pages/product.astro`

- [ ] **Step 1: Create the page**

```astro
---
import Base from '../layouts/Base.astro';
import WorkflowTable from '../components/WorkflowTable.astro';
---

<Base
  title="Product"
  description="How a quant actually uses pyquant.io — an 11-step map of the research-to-production workflow with honest value labels."
>
  <h1 class="text-2xl font-semibold text-[#1a365d]">How a quant uses it</h1>
  <p class="mt-3 max-w-3xl text-sm leading-relaxed text-gray-700">
    Eleven steps in the daily workflow of a quant at a $1B-AUM systematic equity fund, mapped to where the platform helps
    and where it is neutral. We labelled each step with an honest value level — including the steps where we are
    <em>table-stakes</em> or <em>none</em> — so you can see where the bottleneck actually is.
  </p>

  <div class="mt-8">
    <WorkflowTable />
  </div>

  <section class="mt-12 max-w-3xl space-y-4 text-sm leading-relaxed text-gray-700">
    <h2 class="text-lg font-semibold text-[#1a365d]">The central value prop</h2>
    <p>
      Step 9 is the headline. Today, promoting a trained model to production is a multi-week back-and-forth between the
      quant who trained it and the engineer who re-implements the feature code in the serving pipeline. Every team rediscovers
      the same class of bug: the feature that worked in the notebook produces different numbers in production.
    </p>
    <p>
      With pyquant.io there is <strong>no hand-off</strong>. The Python function that computes a feature at training time
      is the same function that runs at serving time — it travels with the model artefact as an MLflow <code>pyfunc</code>
      wrapper. The quant promotes the model in the registry UI. The audit log records the promotion. The serving role
      lazy-reloads. End-to-end in seconds.
    </p>
    <h2 class="text-lg font-semibold text-[#1a365d]">We are not a model-research accelerator</h2>
    <p>
      A quant who already has a great Transformer architecture does not become a better quant by using our platform. A quant
      who has a great architecture and currently spends 60% of their time fighting infrastructure becomes 2.5&times; more
      productive on alpha research because we eliminate the infrastructure tax.
    </p>
  </section>
</Base>
```

- [ ] **Step 2: Build + preview + commit**

```bash
pnpm run lint && pnpm run build
pnpm run preview  # eyeball /product/
# Ctrl+C
git add -A && git commit -m "feat: product page with workflow table"
```

---

### Task 9: Architecture (`/architecture/`)

**Files:**
- Create: `pyquant-site/src/pages/architecture.astro`

- [ ] **Step 1: Create the page**

Content derived from `blueprint/src/02-key-ideas.md` and `blueprint/src/01-executive-summary.md`. The three section headers match the three differentiators verbatim — the Architecture page is the "show your work" for Home's cards.

```astro
---
import Base from '../layouts/Base.astro';
---

<Base
  title="Architecture"
  description="The three load-bearing differentiators with the technical substance — silo tenancy, open-source stack, quant-native defaults."
>
  <h1 class="text-2xl font-semibold text-[#1a365d]">Architecture</h1>
  <p class="mt-3 max-w-3xl text-sm leading-relaxed text-gray-700">
    The three differentiators from the home page, with the substance you probably want to see before the second sales
    meeting. Every claim here corresponds to a chapter in our technical blueprint; sections link to primary sources where
    they exist.
  </p>

  <!-- 1 -->
  <section id="silo-byoc" class="mt-12 max-w-3xl space-y-4 text-sm leading-relaxed text-gray-700">
    <h2 class="text-lg font-semibold text-[#1a365d]">1. Silo + BYOC by default</h2>
    <p>
      Every tenant receives a dedicated GCP project containing a dedicated Cloud Run service set, Cloud SQL instance, GCS
      buckets, and Secret Manager namespace. There is no shared database, no shared application process, no row-level
      security policy. Tenant separation is achieved by separate deployments, not by runtime filters inside shared
      infrastructure. Optional Bring-Your-Own-Cloud puts the entire tenant project in your GCP organisation, with the vendor
      holding limited-scope deployment access only.
    </p>
    <p>
      The alternative — pool tenancy with row-level security — is operationally cheaper at low customer count and is the
      default choice for consumer SaaS. It is the wrong choice here: hedge fund security teams reject multi-tenant SaaS for
      production-grade workloads, and LP questionnaires increasingly ask about data residency and tenancy isolation. We
      pay for a control plane so that silo stays operationally credible at scale.
    </p>
  </section>

  <!-- 2 -->
  <section id="open-source" class="mt-12 max-w-3xl space-y-4 text-sm leading-relaxed text-gray-700">
    <h2 class="text-lg font-semibold text-[#1a365d]">2. Open-source-first stack</h2>
    <p>
      Polars (data frames), Postgres with extensions (PGMQ, Apache AGE, TimescaleDB, pg_cron), MLflow (model registry),
      Dagster (asset orchestration), FastAPI + Pydantic (API), Vite + React + Tailwind + shadcn (UI), uv (Python packaging),
      Cloud Run (runtime). Every load-bearing component is open-source with permissive licensing.
    </p>
    <p>
      This means you can, in principle, pull your stack out of our managed offering and run it yourself on equivalent
      infrastructure. A fund that wants to bring infrastructure in-house in three years can do so without a re-platforming
      exercise. We give up the lock-in revenue that proprietary competitors enjoy and win on land/expand mechanics instead.
    </p>
  </section>

  <!-- 3 -->
  <section id="quant-native" class="mt-12 max-w-3xl space-y-4 text-sm leading-relaxed text-gray-700">
    <h2 class="text-lg font-semibold text-[#1a365d]">3. Quant-native, not generic MLOps</h2>
    <p>
      Specific platform properties, not add-ons:
    </p>
    <ul class="list-disc space-y-2 pl-6">
      <li>
        <strong>PBO / DSR on every backtest.</strong> Bailey &amp; López de Prado's Probability of Backtest Overfitting and
        Deflated Sharpe Ratio are computed automatically; results are surfaced in the run-detail UI.
      </li>
      <li>
        <strong>Walk-forward as a promotion gate.</strong> Models without walk-forward evidence cannot be promoted. Not a
        warning; a block.
      </li>
      <li>
        <strong>CPCV instead of vanilla k-fold.</strong> Combinatorial Purged Cross-Validation with embargo, so training
        data doesn't leak into test via temporally-adjacent samples.
      </li>
      <li>
        <strong>Bi-temporal data discipline.</strong> Every silver and gold row carries <code>_knowable_at</code> (system
        time — when the datum became visible to the platform), <code>_valid_from</code>, and <code>_valid_to</code>.
        Training-data queries without a <code>_knowable_at</code> filter fail pipeline validation before they ever run.
      </li>
      <li>
        <strong>Factor decomposition built in.</strong> Carhart four-factor by default; Hou-Mo-Xue-Zhang q-factor as
        alternative; reports generated with the model, not as a bolt-on.
      </li>
      <li>
        <strong>MLflow <code>pyfunc</code> parity.</strong> The Python callable used at training time is the same callable
        used at serving time, packaged into the artefact. Train-serve skew ceases to exist as a class of bug.
      </li>
      <li>
        <strong>Cryptographic audit chain.</strong> The audit log is hash-chained and exportable to WORM GCS for regulated
        tenants.
      </li>
    </ul>
    <p>
      These are the properties that separate a generic MLOps tool from a quant-native platform. A prospect can tell within
      90 seconds of seeing the UI whether the platform was built by people who know the field.
    </p>
  </section>

  <section class="mt-16 max-w-3xl text-sm text-gray-600">
    <p>
      For the full architecture — medallion data platform, CQRS event store on Postgres, single-image-many-roles,
      blue/green Cloud Run revisions, federated OIDC, control plane — the technical blueprint is the source document. A
      download link will appear here when the blueprint is considered final.
    </p>
  </section>
</Base>
```

- [ ] **Step 2: Build + preview + commit**

```bash
pnpm run lint && pnpm run build && git add -A && git commit -m "feat: architecture page"
```

---

### Task 10: Comparisons (`/comparisons/`)

**Files:**
- Create: `pyquant-site/src/pages/comparisons.astro`

- [ ] **Step 1: Create the page**

```astro
---
import Base from '../layouts/Base.astro';
import ComparisonTable from '../components/ComparisonTable.astro';
---

<Base
  title="Comparisons"
  description="Honest head-to-head vs SigTech, Domino, Palantir Foundry, Databricks, and build-your-own — what each wins on, what we win on, and what we punt on."
>
  <h1 class="text-2xl font-semibold text-[#1a365d]">Comparisons</h1>
  <p class="mt-3 max-w-3xl text-sm leading-relaxed text-gray-700">
    The most expensive marketing mistake in our category is being mistaken for one of the bigger competitors. This page
    exists to prevent that. For each credible alternative we state what they win on, what we win on, and what we
    deliberately punt on. If you read this page and decide a different platform is the right fit, that is a useful
    outcome — no platform should want a customer it cannot serve well.
  </p>

  <div class="mt-10">
    <ComparisonTable />
  </div>

  <section class="mt-16 max-w-3xl space-y-4 text-sm leading-relaxed text-gray-700">
    <h2 class="text-lg font-semibold text-[#1a365d]">Why three load-bearing differentiators and not seven</h2>
    <p>
      The blueprint enumerates ten architectural bets. Three are promoted to differentiator status because a customer
      would plausibly choose us over a competitor because of them. The other seven (Postgres-centric substrate, CQRS,
      single-image-many-roles, federated OIDC, blue/green deployment, control plane, medallion data platform) are sound
      engineering decisions that <em>enable</em> the three differentiators. They are not, in themselves, customer value
      props. A customer never says "I bought this because it uses CQRS."
    </p>
    <p>
      The three differentiators are also chosen so that a competitor who matches one does not automatically match the
      others. SigTech adding silo still leaves them proprietary and generic-ML-ish. Domino adding PBO/DSR still leaves
      them proprietary and multi-tenant. The three together are the moat.
    </p>
  </section>
</Base>
```

- [ ] **Step 2: Build + commit**

```bash
pnpm run lint && pnpm run build && git add -A && git commit -m "feat: comparisons page"
```

---

### Task 11: Principles (`/principles/`)

**Files:**
- Create: `pyquant-site/src/pages/principles.astro`

- [ ] **Step 1: Create the page**

Content derived from `blueprint/positioning/2026-04-21-positioning.md §3` and §4.4. NO NAMES.

```astro
---
import Base from '../layouts/Base.astro';
import { contactEmail } from '../data/nav';
---

<Base
  title="Principles"
  description="What we are, what we are not, what we believe. The discipline behind the product."
>
  <h1 class="text-2xl font-semibold text-[#1a365d]">Principles</h1>
  <p class="mt-3 max-w-3xl text-sm leading-relaxed text-gray-700">
    A short, honest statement of what we are, what we are not, and which customers we can serve well.
  </p>

  <section class="mt-10 max-w-3xl space-y-4 text-sm leading-relaxed text-gray-700">
    <h2 class="text-lg font-semibold text-[#1a365d]">What we believe</h2>
    <ul class="list-disc space-y-2 pl-6">
      <li>Quant-native discipline — walk-forward, PBO, DSR, CPCV, bi-temporal data — is a platform property, not a configurable add-on. If it is optional, it will be skipped.</li>
      <li>Infrastructure isolation beats application-layer multi-tenancy for production-grade workloads. Silo is expensive and correct.</li>
      <li>Your backtest should survive its own promotion to production. <code>_knowable_at</code> filtering at query-build time is not discretion; it is a query-planner rule.</li>
      <li>The research notebook and the production serving path must run the same function. Train-serve skew is a class of bug we close structurally.</li>
      <li>The stack must be reproducible on a laptop. A cloud-only service that can't be emulated locally is disqualified from the architecture.</li>
      <li>Open source is the default. Lock-in revenue is an easier business model; we chose the harder one because our customers prefer it.</li>
    </ul>
  </section>

  <section class="mt-12 max-w-3xl space-y-3 text-sm leading-relaxed text-gray-700">
    <h2 class="text-lg font-semibold text-[#1a365d]">What we are not</h2>
    <ul class="list-disc space-y-2 pl-6">
      <li>Not a notebook environment. Marimo and Jupyter exist; we embed them, we don't rebuild them.</li>
      <li>Not a backtest library. vectorbt and QSTrader exist; we wrap them with PBO/DSR/walk-forward enforcement.</li>
      <li>Not a research environment. Researchers do early-stage exploration anywhere; we accept research output, we don't dictate research process.</li>
      <li>Not a custom-orchestration shop. The platform's view of state is Dagster's asset graph. Dagster does orchestration; we don't re-implement it.</li>
      <li>Not a generic MLOps tool. Our defaults are quant, not medical imaging, not NLP for customer service.</li>
      <li>Not a hedge fund. We don't invest; we don't take management fees; we don't have proprietary alpha. We are infrastructure.</li>
    </ul>
  </section>

  <section class="mt-12 max-w-3xl space-y-3 text-sm leading-relaxed text-gray-700">
    <h2 class="text-lg font-semibold text-[#1a365d]">Customers we can't serve well</h2>
    <p>A short list, said plainly:</p>
    <ul class="list-disc space-y-2 pl-6">
      <li>Enterprise-tier hedge funds ($20B+ AUM, 50+ engineers). You can build this yourselves; you should.</li>
      <li>Retail systematic traders. The floor cost of silo tenancy is wrong for you; QuantConnect and Alpaca serve that segment.</li>
      <li>Multi-asset macro funds whose primary workflow is discretionary with systematic overlay. Our workflow shape is cross-sectional alpha; you would fight us.</li>
      <li>Funds entirely on AWS who refuse GCP. GCP is our default substrate.</li>
    </ul>
  </section>

  <section class="mt-16 max-w-3xl text-sm text-gray-700">
    <p>
      If you think we might fit,
      <a href={`mailto:${contactEmail}`} class="font-medium underline-offset-2 hover:text-[#1a365d] hover:underline">email us.</a>
    </p>
  </section>
</Base>
```

- [ ] **Step 2: Build + commit**

```bash
pnpm run lint && pnpm run build && git add -A && git commit -m "feat: principles page"
```

---

### Task 12: Media (`/media/`)

**Files:**
- Create: `pyquant-site/src/pages/media.astro`

- [ ] **Step 1: Create the page**

```astro
---
import Base from '../layouts/Base.astro';
import MediaEmbed from '../components/MediaEmbed.astro';
---

<Base
  title="Media"
  description="Long-form walk-throughs of the platform and the research-to-production problem it solves."
>
  <h1 class="text-2xl font-semibold text-[#1a365d]">Media</h1>
  <p class="mt-3 max-w-3xl text-sm leading-relaxed text-gray-700">
    Two deep-dives generated from the blueprint. The video is an eight-minute overview; the podcast is a forty-seven-minute
    conversation between two AI hosts on the research-to-production hand-off problem and how this platform addresses it.
    Both are self-hosted — no third-party trackers.
  </p>

  <section class="mt-10 space-y-8">
    <MediaEmbed
      kind="video"
      src="/media/video.mp4"
      title="Modern Quant Platform — 8 min overview"
      description="Eight-minute walk-through of the platform's shape: silo tenancy, open-source stack, quant-native defaults, and the shape of the MVP."
    />

    <MediaEmbed
      kind="audio"
      src="/media/podcast.m4a"
      title="Fixing the research-to-production handoff — 47 min podcast"
      description="Two-host conversation on why the quant-to-engineer hand-off is the most expensive moment in a systematic fund's workflow and what it looks like to close that gap at the platform layer."
    />
  </section>
</Base>
```

- [ ] **Step 2: Build + commit**

```bash
pnpm run lint && pnpm run build && git add -A && git commit -m "feat: media page"
```

**Note:** the media files are not in the repo yet; the embeds will render broken until Task 16 uploads them to the server. That's expected.

---

## Phase 4 — CI and deploy workflows (Tasks 13–14)

### Task 13: CI workflow (lint + build on every PR and push)

**Files:**
- Create: `pyquant-site/.github/workflows/ci.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Lint (astro check + prettier)
        run: pnpm run lint

      - name: Build
        run: pnpm run build

      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
          retention-days: 7
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml && git commit -m "ci: lint + build on push and PR (hosted runner)"
```

---

### Task 14: Deploy workflow (self-hosted runner, rsync to /srv/pyquant/site)

**Files:**
- Create: `pyquant-site/.github/workflows/deploy.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  deploy:
    runs-on: [self-hosted, pyquant-site]
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Build
        run: pnpm run build

      - name: rsync dist/ to /srv/pyquant/site
        run: |
          rsync -a --delete \
            --exclude='media/' \
            dist/ /srv/pyquant/site/
          echo "Deploy complete."

      - name: Verify site responds
        run: |
          curl -sfI https://pyquant.io/ | head -1
          curl -sfI https://pyquant.io/product/ | head -1
          curl -sfI https://pyquant.io/media/ | head -1
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yml && git commit -m "ci: deploy on push-main via self-hosted runner (rsync to /srv/pyquant/site)"
```

- [ ] **Step 3: Push everything so far to GitHub**

```bash
git push -u origin main
```
Expected: all commits from Tasks 1–14 appear on the GitHub repo. The CI workflow will run on the push; it should pass. The deploy workflow will attempt to run and will fail — the self-hosted runner isn't registered with the `pyquant-site` label yet. That's expected; Task 17 fixes it.

**Checkpoint:** the CI workflow is green. Deploy workflow is queued-waiting-for-runner or failed-no-runner — both fine; move on.

---

## Phase 5 — Server-side prerequisites (Tasks 15–18)

These tasks happen via SSH to `ubuntu-server.local` (user `igor`).

### Task 15: Create `/srv/pyquant/site/` on the server

**Server-side task.**

- [ ] **Step 1: SSH in and create the directory**

```bash
ssh igor@ubuntu-server.local
# then on the server:
sudo mkdir -p /srv/pyquant/site/media
sudo chown -R igor:igor /srv/pyquant
# Placeholder so Caddy doesn't serve a 403 while the first deploy is in flight
cat > /srv/pyquant/site/index.html <<'EOF'
<!doctype html><html><head><meta charset=utf-8><title>pyquant.io — deploy pending</title></head>
<body><p style="font-family:system-ui;padding:2rem;">pyquant.io — deploy pending.</p></body></html>
EOF
ls -la /srv/pyquant/site/
```
Expected: `index.html` + empty `media/` directory, both owned by `igor`.

**Checkpoint:** `ls -la /srv/pyquant/site/` shows the placeholder and `media/`.

---

### Task 16: Upload media files to the server

**From the Mac** (run from `~/Downloads`).

- [ ] **Step 1: scp the two files with canonical names**

```bash
scp "/Users/igormusic/Downloads/Modern_Quant_Platform.mp4" igor@ubuntu-server.local:/srv/pyquant/site/media/video.mp4
scp "/Users/igormusic/Downloads/Fixing_the_research_to_production_handoff.m4a" igor@ubuntu-server.local:/srv/pyquant/site/media/podcast.m4a
```

- [ ] **Step 2: Verify on the server**

```bash
ssh igor@ubuntu-server.local 'ls -la /srv/pyquant/site/media/'
```
Expected: `video.mp4` (~25 MB) and `podcast.m4a` (~87 MB), both owned by `igor`.

**Checkpoint:** Both files exist on the server at `/srv/pyquant/site/media/{video.mp4,podcast.m4a}`.

---

### Task 17: Register the self-hosted runner for pyquant-site

**Approach:** run a second runner container scoped to the pyquant-site repo, alongside the existing `quant-runner`. This keeps blast radius small (a compromised workflow in one repo cannot cross into the other's checkout).

- [ ] **Step 1: Get a registration token for the pyquant-site repo**

On the Mac:
```bash
gh api -X POST -H "Accept: application/vnd.github+json" \
  /repos/FreeSideNomad/pyquant-site/actions/runners/registration-token
```
Copy the `.token` value from the JSON. It's single-use and expires in an hour.

- [ ] **Step 2: Inspect the existing runner container's compose/run config**

```bash
ssh igor@ubuntu-server.local 'docker inspect quant-runner --format "{{json .Config.Env}}" | python3 -m json.tool'
ssh igor@ubuntu-server.local 'docker inspect quant-runner --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}"'
```
Note the image tag, labels, and where the runner config lives (usually `/srv/quant-runner/docker-compose.yml` or similar).

- [ ] **Step 3: Create `/srv/pyquant-runner/` with a compose file**

```bash
ssh igor@ubuntu-server.local
# on the server:
sudo mkdir -p /srv/pyquant-runner
sudo chown igor:igor /srv/pyquant-runner
cd /srv/pyquant-runner
cat > compose.yml <<'EOF'
services:
  runner:
    image: myoung34/github-runner:latest
    container_name: pyquant-runner
    restart: unless-stopped
    environment:
      REPO_URL: https://github.com/FreeSideNomad/pyquant-site
      RUNNER_NAME: pyquant-runner
      RUNNER_TOKEN: ${RUNNER_TOKEN}
      RUNNER_WORKDIR: /tmp/runner/work
      RUNNER_SCOPE: repo
      LABELS: self-hosted,linux,x64,pyquant-site
      DISABLE_AUTO_UPDATE: "true"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /srv/pyquant/site:/srv/pyquant/site
      - runner-work:/tmp/runner/work

volumes:
  runner-work:
EOF
```

- [ ] **Step 4: Write the one-shot `.env` with the registration token**

```bash
umask 077
printf 'RUNNER_TOKEN=%s\n' '<paste token from Step 1>' > /srv/pyquant-runner/.env
chmod 600 /srv/pyquant-runner/.env
```

- [ ] **Step 5: Start the runner**

```bash
cd /srv/pyquant-runner
docker compose up -d
docker logs -f pyquant-runner 2>&1 | head -30
```
Expected: logs show `√ Connected to GitHub`, `√ Runner successfully added`, `Listening for Jobs`.

- [ ] **Step 6: Verify on GitHub**

From the Mac:
```bash
gh api /repos/FreeSideNomad/pyquant-site/actions/runners \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); [print(r["name"], r["status"], r["labels"]) for r in d["runners"]]'
```
Expected: `pyquant-runner online [{"name":"self-hosted"}, {"name":"linux"}, {"name":"x64"}, {"name":"pyquant-site"}]`.

- [ ] **Step 7: Scrub the token from `.env`**

The token is single-use, already consumed — but overwriting with a placeholder prevents confusion later:
```bash
ssh igor@ubuntu-server.local 'echo "# Token consumed on first start; runner state now in _work/.runner" > /srv/pyquant-runner/.env'
```

**Checkpoint:** `gh api` call returns the runner as online. The runner has `pyquant-site` in its labels.

---

### Task 18: Swap the Caddy apex block to `file_server`

**Server-side task.**

- [ ] **Step 1: SSH + backup Caddyfile**

```bash
ssh igor@ubuntu-server.local
cd /srv/ledgertm
cp Caddyfile Caddyfile.bak.$(date +%s)
```

- [ ] **Step 2: Edit the `pyquant.io` block**

Open `/srv/ledgertm/Caddyfile`. Find the block that begins `pyquant.io {`. Replace the entire block (from `pyquant.io {` to its closing `}`) with:

```caddy
pyquant.io {
    import tls_cf_pyquant
    encode gzip zstd
    root * /srv/pyquant/site
    file_server {
        index index.html
    }
    header /assets/* Cache-Control "public, max-age=31536000, immutable"
    header / Cache-Control "public, max-age=300"
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "interest-cohort=()"
    }
    log {
        output file /var/log/caddy/pyquant-access.log {
            roll_size 10MiB
            roll_keep 5
        }
        format console
    }
}
```

Leave the `www.pyquant.io` (301 redirect) and `idp.pyquant.io` (reverse-proxy to IdP) blocks unchanged.

- [ ] **Step 3: Validate the Caddyfile**

```bash
IMG=$(docker inspect ledgertm-caddy --format '{{.Image}}')
docker run --rm --env-file /srv/ledgertm/.env \
  -v /srv/ledgertm/Caddyfile:/etc/caddy/Caddyfile:ro "$IMG" \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile 2>&1 | tail -6
```
Expected last line: `Valid configuration`.

- [ ] **Step 4: Hot-reload Caddy (no container recreate needed — only Caddyfile changed, env unchanged)**

```bash
docker exec ledgertm-caddy caddy reload --config /etc/caddy/Caddyfile
```
Expected: returns silently with exit 0. No new cert should need to be issued (pyquant.io cert already issued earlier).

- [ ] **Step 5: Verify from the Mac**

```bash
curl -sI https://pyquant.io/ | head -1
curl -sI https://pyquant.io/media/video.mp4 | grep -E 'Content-Length|Content-Type|Accept-Ranges'
curl -sI https://pyquant.io/ | grep -iE 'strict-transport|x-content-type|referrer-policy|permissions-policy'
```
Expected: HTTP/2 200 for apex and media; security headers present on apex.

Opening `https://pyquant.io/` in a browser at this point shows the Task 15 placeholder until the deploy action runs in Task 19.

**Rollback (this task only):** `cp Caddyfile.bak.<ts> Caddyfile && docker exec ledgertm-caddy caddy reload --config /etc/caddy/Caddyfile`.

**Checkpoint:** apex serves with the new security headers.

---

## Phase 6 — Trigger the first deploy + verify end-to-end (Task 19)

### Task 19: Trigger deploy workflow + verify

- [ ] **Step 1: Trigger the deploy workflow**

From the Mac:
```bash
cd ~/code/pyquant-site
gh workflow run deploy.yml --ref main
# wait a few seconds for it to start, then:
gh run watch
```
Expected: the deploy job runs on `pyquant-runner`, installs pnpm deps, builds, rsyncs. Every step green.

- [ ] **Step 2: Verify all six pages in a browser**

```bash
for p in / /product/ /architecture/ /comparisons/ /principles/ /media/; do
    printf '%-20s  %s\n' "$p" "$(curl -sI "https://pyquant.io$p" | head -1 | tr -d '\r')"
done
```
Expected: every line shows `HTTP/2 200`.

Open each page in a real browser (Safari + Chrome, desktop + phone). Eyeball:
- Nav shows six links; active link is the current page.
- Footer shows current year + `Email us` link that opens the mail composer.
- On `/media/`, click play on the video — it plays. Click play on the audio — it plays.
- Read one full page of prose (Comparisons is longest); kerning/leading feels like banking-demo.
- No console errors in DevTools (there should be zero — no client-side JS at all).

- [ ] **Step 3: Confirm no JavaScript leaked accidentally**

```bash
for p in / /product/ /architecture/ /comparisons/ /principles/ /media/; do
    count=$(curl -s "https://pyquant.io$p" | grep -c '<script')
    echo "$p  scripts=$count"
done
```
Expected: `scripts=0` on every page.

- [ ] **Step 4: Smoke-test media streaming**

```bash
# Range request — must succeed (scrubbing depends on this)
curl -sI -H "Range: bytes=0-1000" https://pyquant.io/media/video.mp4 | head -3
curl -sI -H "Range: bytes=0-1000" https://pyquant.io/media/podcast.m4a | head -3
```
Expected: `HTTP/2 206` (partial content) for both.

**Checkpoint:** site is live at https://pyquant.io; all six pages; media plays; security headers present; no JS.

---

## Phase 7 — Documentation (Task 20)

### Task 20: Write the repo README

**Files:**
- Create: `pyquant-site/README.md`

- [ ] **Step 1: Write the README**

```markdown
# pyquant-site

Static marketing site for [pyquant.io](https://pyquant.io). Built with Astro 5 + Tailwind v4. Deployed to ubuntu-server via a self-hosted GitHub Actions runner.

## Local development

Prerequisites: Node 20+, pnpm 9+.

\`\`\`bash
pnpm install
pnpm run dev        # http://localhost:4321/
pnpm run build      # static output in dist/
pnpm run preview    # preview the built site
pnpm run lint       # astro check + prettier
pnpm run format     # prettier --write
\`\`\`

## Structure

- \`src/pages/\` — one Astro file per page (Home / Product / Architecture / Comparisons / Principles / Media).
- \`src/layouts/Base.astro\` — shared \`<head>\`, nav, footer.
- \`src/components/\` — shared UI (cards, tables, media embeds).
- \`src/data/\` — typed data files for differentiators, workflow steps, comparisons. Edit these, not the page files, for content updates.
- \`src/styles/tokens.css\` — Tailwind v4 \`@theme\` block. Mirrors \`/Users/igormusic/code/banking-demo/src/index.css\`.
- \`public/\` — static assets (favicon). \`public/media/\` is gitignored; media files live only on the server.

## Content sources

Copy is derived from, not verbatim from:

- \`/Users/igormusic/code/quant-platform/blueprint/positioning/2026-04-21-positioning.md\` — load-bearing positioning doc.
- \`/Users/igormusic/code/quant-platform/blueprint/src/02-key-ideas.md\` — ten architectural bets as customer outcomes.
- \`/Users/igormusic/code/quant-platform/blueprint/src/01-executive-summary.md\` — top-level product description.

See \`docs/SPEC.md\` for the full design spec. See \`docs/start.md\` for session kickoff instructions for new LLM sessions.

## Deploy

- Push to \`main\` → \`.github/workflows/deploy.yml\` runs on the self-hosted runner \`pyquant-runner\` → rsync to \`/srv/pyquant/site/\` on ubuntu-server → Caddy serves the new files immediately.
- \`public/media/\` is excluded from the rsync so media files (uploaded out-of-band) aren't wiped.
- Rollback: \`git revert\` + push triggers a re-deploy of the previous revision. For a faster rollback, manually rsync a previous \`dist/\` (artefact retained 7 days from CI).

## Non-goals

No JavaScript framework (pure Astro components, zero client JS). No third-party analytics or trackers. No testimonials, no personal names, no mailing-list signup, no pricing page, no blog. See \`docs/SPEC.md\` §"Not in scope".
```

- [ ] **Step 2: Commit + push**

```bash
git add README.md
git commit -m "docs: repo README with local dev, structure, deploy, non-goals"
git push origin main
```

---

## Self-review (completed by plan author)

- **Spec coverage:**
  - 6 pages (spec §1) → Tasks 7–12 (one per page).
  - Banking-demo tokens (spec §2) → Task 2 (tokens.css mirrors banking-demo's `@theme` block verbatim).
  - Restrained hero (spec §2 "Hero (restrained)") → Task 7 (single line, paragraph, accent underline; no gradient/illustration/large CTA).
  - Copy tone + no names (spec §3) → Task 5 data/nav.ts (mailto target, no names), all page tasks (derived from blueprint, no marketing-speak, no testimonials, no "free trial").
  - Astro 5 + Tailwind v4 + pnpm (spec §4) → Tasks 1, 2.
  - Component + data file structure (spec §4) → Tasks 5, 6.
  - CI/CD via self-hosted runner (spec §5) → Tasks 13, 14, 17.
  - Media files out of git (spec §6) → Task 1 (.gitignore entry), Task 16 (out-of-band upload), Task 12 (references `/media/video.mp4` and `/media/podcast.m4a`).
  - Caddy change (spec §7) → Task 18.
  - Security headers (spec §8) → Task 18 (HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy).
  - Verification (spec "Verification") → Task 19 (all six bullets from the spec mapped to commands).
  - Rollback (spec "Rollback") → Task 18 step "Rollback (this task only)"; Task 19 README section documents the git-revert path.
- **Placeholder scan:** Only runtime value is `<paste token from Step 1>` in Task 17 Step 4 — an intentional human-fill from the API call in Step 1. No TODOs, no "similar to Task N", no generic "handle errors" hand-waves. Every code block is complete and copy-pastable.
- **Type / name consistency:** `navItems`, `contactEmail`, `differentiators`, `workflow`, `comparisons` are defined in `src/data/` in Tasks 5 and 6 and imported by exact name in Tasks 7–12. `DifferentiatorCard` / `WorkflowTable` / `ComparisonTable` / `MediaEmbed` are created in Task 6 and used in Tasks 7, 8, 10, 12 with matching prop names (`d`, no props, no props, `kind`/`src`/`title`/`description`). Tailwind token names (`--color-primary`, etc.) match banking-demo's exactly.
- **Gap:** None found. The only deferred item (the downloadable blueprint PDF link on Architecture page) is explicitly flagged in the spec's "Open questions" section and deliberately not included in Task 9.
