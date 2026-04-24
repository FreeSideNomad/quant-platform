# pyquant.io marketing site — design

**Date:** 2026-04-24
**Status:** Design awaiting user approval.
**Scope:** A 6-page static marketing site for pyquant.io, sharing the design language of the banking-demo project, sourced from the positioning doc and key-ideas chapter of `/blueprint/`. Hosted on the existing home-lab Caddy instance.
**Not in scope:** Control-plane routing on `pyquant.io` (planned later — 2-line Caddyfile edit when needed); pricing page; blog; docs portal; testimonials; mailing-list signup; any JavaScript framework; CMS; dark mode; analytics beyond Caddy access logs; any personally-identifying copy (no founder names or bios).

## Goal

Give `pyquant.io` a restrained, information-dense marketing site that:

- Proves technical credibility to the target buyer (head of quant technology, $500M–$5B AUM systematic fund) in under two minutes.
- Reuses the design system from `/Users/igormusic/code/banking-demo` so the site looks like a serious tool, not a SaaS landing page.
- Hosts two pieces of NotebookLM-generated collateral (video + long-form audio) self-served from the same Caddy.
- Ships as plain static HTML + CSS — no client-side JS, no third-party trackers, no framework runtime.
- Lives in its own repo (`FreeSideNomad/pyquant-site`) and deploys by GitHub Action rsync to the Caddy volume.

## Source material

The site draws from material already in the quant-platform repo. Marketing copy is *derived from*, not copied verbatim out of, these sources:

- **`blueprint/positioning/2026-04-21-positioning.md`** — one-sentence pitch (§1), buyer profile (§2), anti-positioning (§3), three differentiators (§4), head-to-head competitor comparisons (§5), workflow-value mapping (§6). The load-bearing source.
- **`blueprint/src/02-key-ideas.md`** — ten architectural bets framed as customer outcomes.
- **`blueprint/src/01-executive-summary.md`** — what the product is, in its cleanest form.
- **`blueprint/diagrams/rendered/*.pdf`** — for any rendered diagram inclusions on the Architecture page.
- **NotebookLM artefacts** (produced 2026-04) — `Modern_Quant_Platform.mp4` (video, 8:36, 25 MB), `Fixing_the_research_to_production_handoff.m4a` (audio, 47:17, 87 MB).

## Design

### 1. Site map

| Page | URL | Primary purpose | Key content | Approx. words |
| ---- | --- | --- | --- | --- |
| Home | `/` | Thirty-second orientation. No hero splash. | Two-paragraph intro; three differentiator cards; one CTA. | 250 |
| Product | `/product/` | "How a quant actually uses this." | 11-step workflow-value table (positioning §6); one narrative "day in the life" passage. | 1000 |
| Architecture | `/architecture/` | Technical credibility. | Three differentiators expanded with real substance (PBO/DSR, walk-forward, CPCV, `_knowable_at`, `pyfunc`, silo+BYOC). One or two rendered diagrams. | 1500 |
| Comparisons | `/comparisons/` | Anti-positioning. | vs SigTech, Domino, Palantir, Databricks, build-your-own. "They win / we win / we punt" format. | 1200 |
| Principles | `/principles/` | What we are, what we are not, what we believe. | Distillation of positioning §3 and §4.4. Contact email. No names. | 600 |
| Media | `/media/` | Deep-dive collateral for serious evaluators. | `<video>` tag for Modern_Quant_Platform.mp4 + `<audio>` tag for the 47-min research-to-production podcast. Two short "what this is" paragraphs. | 150 |

Every page has the same top nav (six links in the same order) and the same footer.

### 2. Visual language — inherit from banking-demo

Matched exactly to `/Users/igormusic/code/banking-demo/src/index.css` and component conventions:

- **Typography:** Inter, system-ui fallback stack. Scale `text-xs` (11 px) through `text-3xl` (30 px). Weights 500 / 600 / 700. No web-font loading (system Inter only, matches banking-demo).
- **Color:** primary navy `#1a365d`; body foreground `#0a0a0a` on `#ffffff`; full `gray-50`–`gray-900` scale; accent blues `#3b82f6` / `#1e40af` / `#93c5fd`; status palette `#16a34a` / `#ef4444` / `#f59e0b`. Light mode only. Navy used only as small accent (logo, active-nav underline), never large surfaces.
- **Spacing + radii:** `gap-{1,2,3,4,6}`, `p-{2,3,4,5,6}`, `space-y-6`. Radii 2 / 3 / 4 / 6 px via `rounded-{sm,md,lg,xl}`.
- **Components:** card = `rounded-lg border border-gray-100 bg-white p-4 shadow-sm transition hover:shadow-md`. Button (used sparingly) = `rounded-lg border border-gray-100 bg-white px-4 py-3 shadow-sm hover:border-blue-200 hover:shadow-md`. Tables get `border-gray-100` rows, `text-sm` content, `text-xs font-semibold text-gray-500 uppercase` headers. Nav active-state is a 3 px right-border indicator (banking-demo sidebar convention, translated here to a 2 px bottom border because the pyquant nav is horizontal).
- **Hero (restrained):** one line at `text-2xl font-semibold` + short paragraph at `text-sm text-gray-600`. Optional single accent underline on one key phrase. No gradient, no illustration, no full-bleed background, no large CTA button. Matches banking-demo's subdued aesthetic; explicit departure from typical SaaS marketing.
- **Information density:** high. Long-form prose stays at `text-sm`/`text-base`, tables stay tight. This is a serious-tool site, not a landing page.

Divergence from banking-demo: banking-demo is an app with a left sidebar. pyquant.io is a public site with a horizontal top nav. Same palette, smaller type on nav, no sidebar.

### 3. Copy tone

- Written for the buyer persona defined in positioning §2.1: a technical leader at a mid-market systematic fund. They want proof the platform was built by people who know the field, not a sales pitch.
- Terms like **PBO, DSR, CPCV, walk-forward validation, `_knowable_at`, `pyfunc`, silo tenancy, DNS-01, BYOC** appear without softening glosses on first use; a brief one-sentence plain-English gloss only on first occurrence when absolutely necessary.
- No "transform your workflow" marketing-speak. No testimonials (none exist). No "start free trial" / "sign up" CTAs. No countdowns, exit-intent modals, scroll-triggered animations.
- Single CTA site-wide: plain text link **"Email us"** → `mailto:freesidenomad@gmail.com`. No large button.
- **No personal names.** Anywhere. No founder bios, no "meet the team," no authored-by bylines. The voice is plural ("we") with no individual attached.
- Honest framing: the Principles and Comparisons pages explicitly name what the platform is not and which customers we don't target. Matches positioning §3.

### 4. Build stack

New repo `FreeSideNomad/pyquant-site` (initially private; public when v1 ships if desired).

- **Framework:** Astro 5 (static output only, no SSR, no islands, no client-side hydration).
- **CSS:** Tailwind v4 via `@tailwindcss/vite`. Design tokens copied from banking-demo's `src/index.css` `@theme` block into a single `src/styles/tokens.css`.
- **Package manager:** `pnpm` (matches banking-demo).
- **Content:** each page is a single `.astro` file in `src/pages/`. Longer copy blocks (the workflow-value table, the comparison tables) live in MDX or as typed TypeScript data files imported into the page.
- **Shared UI:** `src/layouts/Base.astro` holds `<html>`, `<head>`, nav, and footer. Page-specific components (`DifferentiatorCard.astro`, `ComparisonTable.astro`, `WorkflowTable.astro`, `MediaEmbed.astro`) live in `src/components/`.
- **No JavaScript runtime.** Astro outputs pure HTML + CSS; any JS-requiring feature is out of scope.

```
pyquant-site/
├── astro.config.mjs
├── package.json
├── pnpm-lock.yaml
├── tailwind.config.mjs        # tokens inherited; minimal
├── tsconfig.json
├── README.md
├── src/
│   ├── layouts/
│   │   └── Base.astro
│   ├── components/
│   │   ├── Nav.astro
│   │   ├── Footer.astro
│   │   ├── DifferentiatorCard.astro
│   │   ├── WorkflowTable.astro
│   │   ├── ComparisonTable.astro
│   │   └── MediaEmbed.astro
│   ├── pages/
│   │   ├── index.astro
│   │   ├── product.astro
│   │   ├── architecture.astro
│   │   ├── comparisons.astro
│   │   ├── principles.astro
│   │   └── media.astro
│   ├── data/
│   │   ├── differentiators.ts
│   │   ├── workflow.ts
│   │   └── comparisons.ts
│   └── styles/
│       └── tokens.css
├── public/
│   ├── favicon.svg
│   └── (media/ is NOT in git — see §6)
└── .github/
    └── workflows/
        └── deploy.yml
```

### 5. CI/CD via self-hosted runner on ubuntu-server

The ubuntu-server already runs a GitHub Actions self-hosted runner (`quant-runner` container, image `myoung34/github-runner:latest`). The pyquant-site deploy uses that runner directly instead of a GitHub-hosted runner + SSH key, because the runner sits on the same host as the Caddy volume and can write to it without any deploy credentials.

Two workflows in `.github/workflows/`:

**`ci.yml` — validation on every push and pull request (runs on `ubuntu-latest`, the GitHub-hosted free tier):**
1. Checkout.
2. Set up pnpm + Node.
3. `pnpm install --frozen-lockfile`.
4. `pnpm run lint` (Astro's `astro check` + Prettier check).
5. `pnpm run build` — verifies the site builds clean.
6. Upload `dist/` as an artifact for inspection.

Fast, gate-able, doesn't touch production.

**`deploy.yml` — deploy on push to `main` (runs on `self-hosted`):**
1. Checkout.
2. `pnpm install --frozen-lockfile` (pnpm cached on the runner host).
3. `pnpm run build` → `dist/`.
4. `rsync -a --delete --exclude=media/ dist/ /srv/pyquant/site/` — the runner container must have `/srv/pyquant/site` bind-mounted (see below). `--exclude=media/` preserves the large media files uploaded out-of-band.
5. No Caddy reload — `file_server` picks up new files on the next request.

Both workflows `concurrency: group: ${{ github.ref }}` + `cancel-in-progress: true` so rapid pushes don't pile up.

**Runner prerequisites on the server (one-time setup — captured as plan tasks):**
- Register `quant-runner` for the pyquant-site repo (GitHub → repo Settings → Actions → Runners → New self-hosted runner — copy the token into the runner's restart), OR register a second runner scoped to the new repo only.
- Add `/srv/pyquant/site:/srv/pyquant/site` to the runner container's volume list so it can write to the Caddy serving dir. Requires editing the runner's compose/systemd unit and restarting.
- Add `rsync` to the runner image (bundled in `myoung34/github-runner:latest`; verify with `docker exec quant-runner which rsync`).

**Why not GitHub-hosted + SSH key?** Simpler security (no key to leak, no `authorized_keys` command restriction to audit), no Bell-upload latency on artifact upload, and it exercises the self-hosted runner that's already paid for. Trade-off: CI workflow still runs on hosted runners to keep validation off the path if the self-hosted runner is down.

### 6. Media files (NOT committed to git)

Large files don't belong in the marketing repo (Git history bloat, slow clones). They're uploaded once, out of band.

- **`public/media/video.mp4`** — copy of `Modern_Quant_Platform.mp4` (25 MB). Upload once to the server at `/srv/pyquant/site/media/video.mp4`. `public/media/` is in `.gitignore`.
- **`public/media/podcast.m4a`** — copy of `Fixing_the_research_to_production_handoff.m4a` (87 MB). Upload once to `/srv/pyquant/site/media/podcast.m4a`.
- **`/media/` page** uses `<video controls preload="metadata" src="/media/video.mp4">` and `<audio controls preload="metadata" src="/media/podcast.m4a">`. Both tags render without any JavaScript; modern browsers' built-in controls are fine.
- **Filenames deliberately renamed to generic** (`video.mp4` / `podcast.m4a`) so the original NotebookLM filenames don't leak into the URL path.
- Caveat: Bell residential upload (~10–25 Mbps) means first-byte for international visitors is slower than a CDN-backed asset. Acceptable for v1; revisit with Cloudflare Stream or unlisted YouTube if bandwidth becomes a complaint.

### 7. Caddy change on ubuntu-server

Current block on `pyquant.io` reverse-proxies to the BFF. The marketing site takes the apex; the BFF is reachable from the site nav only via a future `/<control-plane-path>/*` route (not wired today).

Replace in `/srv/ledgertm/Caddyfile` (tasks 6 / 7 backup convention from prior work applies):

```caddy
pyquant.io {
    import tls_cf_pyquant
    encode gzip zstd
    root * /srv/pyquant/site
    file_server {
        index index.html
    }
    # Cache-Control for hashed assets vs HTML
    header /assets/* Cache-Control "public, max-age=31536000, immutable"
    header / Cache-Control "public, max-age=300"
    log {
        output file /var/log/caddy/pyquant-access.log {
            roll_size 10MiB
            roll_keep 5
        }
        format console
    }
}
```

`idp.pyquant.io` and `www.pyquant.io` site blocks stay unchanged.

Swap sequence to avoid a 404 window:
1. `mkdir -p /srv/pyquant/site` with an index.html placeholder (or the first real build).
2. Upload media files to `/srv/pyquant/site/media/`.
3. Edit Caddyfile block as above; `docker exec ledgertm-caddy caddy validate && caddy reload`.
4. Verify `curl https://pyquant.io` returns the site, not a BFF redirect.

### 8. Security + privacy posture

- No third-party scripts (no Google Analytics, no Plausible-hosted, no CDN fonts, no font-CDN, no hotjar).
- No client-side JS, so no XSS via site code; only surface is anything a contributor embeds later.
- Caddy already sets reasonable defaults; add `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: interest-cohort=()` via Caddy `header` directive.
- No forms, no cookies, no state. Privacy policy page not required for v1.
- `mailto:` link is the only outbound user action; no tracking on it.

## Verification

After deploy, from the Mac:

```bash
# 1. All six pages 200 and serve HTML
for p in / /product/ /architecture/ /comparisons/ /principles/ /media/; do
    curl -sI "https://pyquant.io$p" | head -1
done

# 2. Media accessible and has Accept-Ranges for scrubbing
curl -sI https://pyquant.io/media/video.mp4 | grep -E 'Content-Length|Accept-Ranges|Content-Type'
curl -sI https://pyquant.io/media/podcast.m4a | grep -E 'Content-Length|Accept-Ranges|Content-Type'

# 3. Security headers present
curl -sI https://pyquant.io/ | grep -iE 'strict-transport|x-content-type|referrer-policy|permissions-policy'

# 4. No accidental JavaScript leak (should return 0)
curl -s https://pyquant.io/ | grep -c '<script'

# 5. Lighthouse-quick (eyeball) — open DevTools, verify first-contentful-paint < 1s on LAN
```

Browser-side spot checks: Safari + Chrome, desktop + phone. Read one full page of prose (Comparisons or Architecture) start to finish; kerning / leading / scan-ability should feel like banking-demo. Play 10 seconds of the video. Play 10 seconds of the podcast; confirm scrubbing works.

## Rollback

Two rollback axes, independently usable:

1. **Caddy-only rollback** — restore the previous `Caddyfile` from the `Caddyfile.bak.<ts>` backup and `caddy reload`. `pyquant.io` reverts to reverse-proxying the BFF. Takes under 30 seconds. `ledgertm.com` routes untouched.
2. **Site-content rollback** — each deploy rsync has a predecessor. The previous `dist/` isn't automatically kept, but Git `HEAD~1` rebuilt and rsynced re-deploys the prior version in ~60 seconds. For one-off bad deploys, `git revert` + push triggers the action.

Media files aren't in git and aren't re-uploaded on deploy (rsync excludes `public/media/`). A botched build cannot break media playback.

## Risks and mitigations

- **Upload bandwidth bottleneck on residential Bell for international visitors** → mitigation: keep media files small; consider Cloudflare Stream ($5/mo) later; use `preload="metadata"` so pages don't auto-download the whole media.
- **Astro / Tailwind v4 upstream churn** → mitigation: pin exact versions in `package.json`; `pnpm-lock.yaml` committed; dependabot can be off for this repo.
- **Self-hosted runner compromised** → mitigation: only the pyquant-site repo can dispatch jobs to it; the runner container has bind access only to `/srv/pyquant/site/` (not the whole filesystem); workflow pins actions by SHA rather than tag so a compromised action version can't rewrite history retroactively.
- **Caddy config typo takes down `pyquant.io`** → mitigation: `caddy validate` (with `--env-file`) before every reload; pre-edit backup is the immediate rollback.
- **Site copy drifts from the canonical positioning doc** → mitigation: a short comment at the top of each page's `.astro` file pointing to the blueprint section it's derived from; a once-a-quarter check.

## Open questions (deferred, not blocking)

- **Control-plane path** (`/app` / `/console` / `/platform` / other) — decide when the BFF is actually ready to be exposed publicly under pyquant.io. Until then, the site has no "Launch app" affordance.
- **Public vs private repo** — ship private first; flip `gh repo edit --visibility public` when copy is vetted.
- **Short-form podcast** (`Infrastructure_is_the_new_quantitative_moat.m4a`, 21 min) — currently not featured to keep the media page focused; add later if useful.
- **Rendered blueprint PDF link** — the full blueprint renders to `blueprint/output/blueprint.pdf`. Worth linking from Architecture or Principles pages as "read the full blueprint" for deep readers. Requires a way to publish that PDF (host on pyquant.io/blueprint.pdf? link to a GitHub release asset?). Deferred to when the blueprint is considered final.
- **SEO meta tags** — minimally present (title, description, og:image placeholder). A favicon and open-graph image still need to be produced; placeholder "pq" wordmark in SVG for now.
