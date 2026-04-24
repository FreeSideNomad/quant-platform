# pyquant.io hosting — design

**Date:** 2026-04-24
**Status:** Design approved; implementation plan to follow.
**Scope:** Serve `pyquant.io` from the existing home-lab ubuntu-server, routing into the running `quant-platform` Docker stack, with automated TLS and dynamic-DNS kept in sync. Dual-home alongside `quant.ledgertm.com` during a short transition.
**Not in scope:** Migrating the quant platform off home-lab infra; marketing/static content on `pyquant.io`; publicly exposing `mock-oidc`; retiring `quant.ledgertm.com` (that is a separate, later change); HA or geo-redundancy.

## Goal

Bring `pyquant.io` (registered via Spaceship 2026-04-24) into the existing home-lab hosting pattern with zero new moving parts:

- Apex `pyquant.io` serves the quant-platform BFF directly.
- `idp.pyquant.io` serves the quant-platform IdP on its own hostname.
- `www.pyquant.io` 301-redirects to apex so browser-typed `www` works.
- Traffic is TLS-terminated with a Let's Encrypt cert issued via Cloudflare DNS-01.
- A cron'd DDNS script keeps the apex A record pointed at the current Bell residential WAN IP.

## Current hosting state (observed 2026-04-24)

Single pattern, already running for `ledgertm.com`, documented on the server at `/home/igor/docs/{ARCHITECTURE,NETWORKING,SERVICES,RUNBOOK}.md`.

- **Host:** `ubuntu-server` (192.168.2.100), Ubuntu 24.04 LTS, Docker 29, user `igor`. Hyper-V guest on `win-server` (192.168.2.250); Windows is a hypervisor only — no web services.
- **Ingress:** Bell router forwards WAN 80/443 TCP + 443 UDP → 192.168.2.100. Public IP is dynamic (`184.144.56.28` at last check).
- **DDNS:** `/home/igor/ddns/update.sh` on a 5-minute cron. Today updates only `ledgertm.com`.
- **Reverse proxy:** one Caddy container (`ledgertm-caddy`), custom-built `caddy:2` + `github.com/caddy-dns/cloudflare` plugin via xcaddy. Binds 80/443 on the host. TLS via DNS-01 using a per-zone Cloudflare API token.
- **Config root:** `/srv/ledgertm/` contains `Dockerfile`, `compose.yml`, `Caddyfile`, `.env`, `site/`, `caddy-data/`, `caddy-config/`, `logs/`.
- **Existing Caddyfile routes:**
  - `ledgertm.com` → 301 to `www.ledgertm.com`
  - `www.ledgertm.com` → static `file_server` (`/srv/ledgertm/site`)
  - `app.ledgertm.com` → `reverse_proxy ledger-gateway:8300`
  - `quant.ledgertm.com` → path-based: `/idp/*` → IdP, `/mock/*` → mock-oidc, else → BFF
- **Backend containers** (already up): `quant-platform-bff-1:8080`, `quant-platform-idp-1:8001`, `quant-platform-mock-oidc-1:9800` on the default docker bridge, reachable from the Caddy container by service name.

Although the config lives under `/srv/ledgertm/`, the Caddy instance is functionally the shared edge proxy. Naming is imperfect; a later refactor to `/srv/caddy/` with per-site fragment files is anticipated but explicitly deferred.

## Design

### Data flow

```
user browser
  → https://pyquant.io                 (Cloudflare DNS, grey-cloud / DNS-only)
  → WAN 184.144.56.28:443               (Bell residential; DDNS keeps this fresh)
  → router port-forward 443 → 192.168.2.100
  → ubuntu-server : ledgertm-caddy     (TLS terminated here; cert from LE via DNS-01)
  → Caddy site block matches Host header:
      pyquant.io         → quant-platform-bff-1:8080
      idp.pyquant.io     → quant-platform-idp-1:8001
      www.pyquant.io     → 301 → https://pyquant.io{uri}
```

No changes to backend containers — they already serve `quant.ledgertm.com` over the same docker network.

### DNS records (Cloudflare, after the zone is created)

| Name              | Type  | Value                                     | Proxied |
| ----------------- | ----- | ----------------------------------------- | ------- |
| `pyquant.io`      | A     | `184.144.56.28` (DDNS-updated every 5 min)| off     |
| `www.pyquant.io`  | CNAME | `pyquant.io`                              | off     |
| `idp.pyquant.io`  | CNAME | `pyquant.io`                              | off     |

Rationale:

- **Single A record** → DDNS only has to update one name per zone; `www`/`idp` inherit via CNAME.
- **Grey-cloud (proxied=off)** matches the existing `ledgertm.com` pattern and keeps DNS-01 straightforward. Orange-cloud can be revisited later if DDoS protection or IP concealment is wanted.

### Caddyfile additions (`/srv/ledgertm/Caddyfile`)

Append (do not replace — existing blocks untouched):

```caddy
(tls_cf_pyquant) {
    tls {
        dns cloudflare {env.CLOUDFLARE_PYQUANT_API_TOKEN}
    }
}

pyquant.io {
    import tls_cf_pyquant
    encode gzip zstd
    reverse_proxy quant-platform-bff-1:8080
    log {
        output file /var/log/caddy/pyquant-access.log {
            roll_size 10MiB
            roll_keep 5
        }
        format console
    }
}

www.pyquant.io {
    import tls_cf_pyquant
    redir https://pyquant.io{uri} permanent
}

idp.pyquant.io {
    import tls_cf_pyquant
    encode gzip zstd
    reverse_proxy quant-platform-idp-1:8001
    log {
        output file /var/log/caddy/pyquant-idp-access.log {
            roll_size 10MiB
            roll_keep 5
        }
        format console
    }
}
```

A separate `tls_cf_pyquant` snippet is required: Cloudflare API tokens are zone-scoped, so the existing `tls_cf` (which uses `CLOUDFLARE_LEDGERTM_API_TOKEN`) cannot issue certs for `pyquant.io`.

### Secrets

Add to `/srv/ledgertm/.env` (so Caddy can read it):

```
CLOUDFLARE_PYQUANT_API_TOKEN=<Zone:DNS:Edit token scoped to pyquant.io only>
```

Add to `/home/igor/ddns/.env` (so the DDNS script can update the A record):

```
CLOUDFLARE_PYQUANT_API_TOKEN=<same token>
CLOUDFLARE_PYQUANT_ZONE_ID=<zone id, copied from Cloudflare dashboard>
```

The Caddy `compose.yml` must surface the new env var to the container. If it currently uses `env_file: .env`, no change. If it whitelists individual vars under `environment:`, add `CLOUDFLARE_PYQUANT_API_TOKEN` there.

### DDNS script change

Refactor `/home/igor/ddns/update.sh` to loop over a list of zones rather than hard-coding one. Intended target shape (pseudo):

```bash
# source .env; define an array of zone records
ZONES=(
  "ledgertm.com|$CLOUDFLARE_LEDGERTM_ZONE_ID|$CLOUDFLARE_LEDGERTM_API_TOKEN"
  "pyquant.io|$CLOUDFLARE_PYQUANT_ZONE_ID|$CLOUDFLARE_PYQUANT_API_TOKEN"
)
for spec in "${ZONES[@]}"; do ...existing logic per zone... ; done
```

Cron cadence unchanged (5 min). The `.last-ip` cache stays shared (single WAN IP regardless of zone count). The script should continue updating subsequent zones if one fails (per-zone try/report, not fail-fast).

### User-owned prereqs

These are done in a browser and cannot be automated from this repo:

1. **Cloudflare** → add `pyquant.io` as a new zone. Note the two assigned nameserver hostnames (e.g., `X.ns.cloudflare.com`, `Y.ns.cloudflare.com`).
2. **Spaceship** → change `pyquant.io` nameservers from Spaceship defaults to the two Cloudflare nameservers from step 1. Propagation typically 15 min–2 hr.
3. **Cloudflare** → mint an API token: permissions `Zone → DNS → Edit`, zone resources = `Include → Specific zone → pyquant.io`. Copy the token once; store it; paste into the two `.env` files on the server.
4. Capture the `pyquant.io` **Zone ID** from the Cloudflare dashboard overview (right side).

Click-path instructions with screenshots belong in the implementation plan/runbook, not the spec.

## Verification

After rollout, from the Mac:

```bash
# DNS
dig +short pyquant.io @1.1.1.1           # expect WAN IP
dig +short www.pyquant.io @1.1.1.1       # expect pyquant.io → WAN IP
dig +short idp.pyquant.io @1.1.1.1       # expect pyquant.io → WAN IP

# TLS + HTTP
curl -sI https://pyquant.io              # 200 or auth-redirect; valid LE cert
curl -sI https://www.pyquant.io          # 301 → https://pyquant.io/
curl -sI https://idp.pyquant.io          # 200 from the IdP

# Caddy logs
ssh igor@ubuntu-server.local 'docker logs ledgertm-caddy --tail 80'
```

Expected Caddy log signals on first startup after config reload:
- `certificate obtained successfully` for `pyquant.io`, `www.pyquant.io`, `idp.pyquant.io` via `acme/dns-01/cloudflare`
- no `errors` at `warn`/`error` level

## Rollback

The Caddyfile is a bind-mounted file, not baked into the image. Rollback is a file copy + config reload:

```bash
cd /srv/ledgertm
cp Caddyfile.bak.<ts> Caddyfile
docker exec ledgertm-caddy caddy reload --config /etc/caddy/Caddyfile
```

Revert takes under 30 s. Existing `ledgertm.com` routes are not edited, so they remain up regardless of whether the pyquant blocks succeed. Backup file should be created before edit using the timestamp convention already visible on the server (`Caddyfile.bak.1776763349`).

If only DDNS fails: pyquant apex A record can be hand-set in Cloudflare; Caddy will still serve traffic the moment DNS resolves.

## Risks and mitigations

- **Cloudflare token with wrong scope** → LE issuance fails silently for hours then errors. Mitigation: test token with `curl -s -H "Authorization: Bearer $TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify` before restarting Caddy.
- **Nameservers not yet propagated at Spaceship** → DNS-01 challenge fails until propagated. Mitigation: verify `dig +short NS pyquant.io` shows Cloudflare nameservers before reloading Caddy; if not, Caddy will retry automatically and succeed once NS propagates.
- **Bell rotates WAN IP during rollout** → LE may succeed but backends unreachable until DDNS ticks. Mitigation: trigger `~/ddns/update.sh` manually once post-edit rather than waiting for cron.
- **Typo in Caddyfile takes down ledgertm routes** → Mitigation: `docker exec ledgertm-caddy caddy validate --config /etc/caddy/Caddyfile` before reload. Backup-copy convention already exists.

## Open questions (deferred, not blocking)

- Orange-cloud (CF proxy) — worth enabling later for DDoS protection and origin-IP concealment? Not needed for launch.
- Observability — should `pyquant.io` access logs ship to the platform's telemetry stack, or stay file-only like ledgertm? Not needed for launch.
- Split `/srv/ledgertm/` into a shared `/srv/caddy/` with per-site config fragments when a 4th site arrives or the single Caddyfile crosses ~200 lines.
