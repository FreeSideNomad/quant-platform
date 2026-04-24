# pyquant.io Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Note:** This is a human-facing ops runbook. Several tasks are browser click-paths at Cloudflare / Spaceship that only you can do. Server-side tasks can be executed by a subagent via SSH once prerequisites are met.

**Goal:** Bring `pyquant.io` online behind the existing Caddy edge proxy on ubuntu-server (192.168.2.100), reverse-proxying to the already-running quant-platform BFF and IdP containers, with TLS issued via Let's Encrypt DNS-01 and DDNS keeping the apex A record fresh.

**Architecture:** Append four blocks to `/srv/ledgertm/Caddyfile` (one TLS snippet, apex, www redirect, idp). Mint a zone-scoped Cloudflare API token, propagate the zone change from Spaceship to Cloudflare, and extend `/home/igor/ddns/update.sh` to update both zones. No new containers, no new ports.

**Tech Stack:** Cloudflare DNS + API, Caddy 2 with `caddy-dns/cloudflare` plugin, Docker Compose, bash cron DDNS. Spec: `docs/superpowers/specs/2026-04-24-pyquant-io-hosting-design.md`.

**Conventions used in this plan:**
- `<YOU>` / `<TOKEN>` / `<ZONE_ID>` / `<WAN_IP>` = runtime values you substitute. Never commit the real values.
- "Click-path:" = in a browser; literal labels in **bold**.
- "On mac:" = run locally. "On server:" = inside `ssh igor@ubuntu-server.local`.
- Every task ends with a **Checkpoint** (how to know it's done) and **Rollback for this task only**.

---

## Phase 1 — Browser prerequisites (10–30 min wall clock)

### Task 1: Add `pyquant.io` as a Cloudflare zone

**Why:** Caddy needs Cloudflare to control DNS for the zone so it can solve the Let's Encrypt DNS-01 challenge and issue a real cert. This is the only way to get TLS before any HTTP request reaches the server.

**Files:** None (browser-only).

- [ ] **Step 1: Log in to Cloudflare**

Click-path: <https://dash.cloudflare.com/> → log in with the same account that already owns `ledgertm.com` and `ivamare.com`.

- [ ] **Step 2: Add site**

Click-path: upper-right **+ Add** → **Existing domain** → enter `pyquant.io` → **Continue** → pick the **Free** plan → **Continue**.

- [ ] **Step 3: Capture assigned nameservers**

Cloudflare will show two nameservers of the form `xxx.ns.cloudflare.com` and `yyy.ns.cloudflare.com`. Copy both into a scratch pad. You'll use them in Task 2.

**Checkpoint:** The zone overview page shows `pyquant.io` with status **Pending Nameserver Update** and the two `*.ns.cloudflare.com` hostnames are visible.

**Rollback:** Cloudflare → zone → **Advanced Actions** → **Delete zone** (no side-effects until nameservers are changed at Spaceship).

---

### Task 2: Change nameservers at Spaceship

**Why:** `pyquant.io` is registered at Spaceship; until its nameservers point at Cloudflare, your Cloudflare zone is inert.

**Files:** None.

- [ ] **Step 1: Log in to Spaceship**

Click-path: <https://spaceship.com/> → **Account** → **Domains** → click `pyquant.io`.

- [ ] **Step 2: Edit nameservers**

On the domain page, find **Nameservers** → **Edit** → select **Custom** (not Spaceship default) → enter the two `*.ns.cloudflare.com` values captured in Task 1.3 → **Save**.

- [ ] **Step 3: Wait for propagation and verify**

On mac, poll until Cloudflare's nameservers appear globally:
```bash
dig +short NS pyquant.io @1.1.1.1
```
Expected (order varies): two `*.ns.cloudflare.com` entries. Typical propagation is 15 min–2 hr. You can proceed to Tasks 3–5 while waiting; do NOT proceed past Task 10 until this returns Cloudflare's nameservers.

**Checkpoint:** `dig NS pyquant.io @1.1.1.1` returns only the two Cloudflare nameservers. In the Cloudflare dashboard, the zone status flips to **Active** (Cloudflare emails you when this happens).

**Rollback:** On Spaceship → same **Edit nameservers** screen → revert to **Spaceship default**. This is only useful if you decide to abandon the Cloudflare setup entirely before going live.

---

### Task 3: Mint a scoped Cloudflare API token for `pyquant.io`

**Why:** One token per zone, least-privilege. If this token leaks, the blast radius is limited to the `pyquant.io` zone — it cannot touch `ledgertm.com`.

**Files:** None (token is generated in browser; pasted into server files in Task 8).

- [ ] **Step 1: Open token creation**

Click-path: Cloudflare dashboard → upper-right avatar → **My Profile** → **API Tokens** (left nav) → **Create Token**.

- [ ] **Step 2: Use the "Edit zone DNS" template**

Scroll to **Edit zone DNS** → **Use template**. This preselects `Zone → DNS → Edit` permissions.

- [ ] **Step 3: Scope to pyquant.io only**

- **Permissions:** leave as `Zone — DNS — Edit` (the template default).
- **Zone Resources:** change from **All zones** → **Include → Specific zone → pyquant.io**.
- **Client IP Address Filtering:** leave empty.
- **TTL:** leave empty (no expiry).

- [ ] **Step 4: Review + create**

Click **Continue to summary** → **Create Token**. Cloudflare will display the token **exactly once**. Copy it immediately to a secure place (password manager or your ssh-into-server clipboard). Referred to below as `<TOKEN>`.

- [ ] **Step 5: Verify the token works**

On mac:
```bash
TOKEN='<paste-token-here>'   # do not commit; this is a local shell var
curl -s -H "Authorization: Bearer $TOKEN" \
     https://api.cloudflare.com/client/v4/user/tokens/verify | jq .
```
Expected: `"success": true` and `"status": "active"`.

Then clear the shell var so it doesn't end up in history: `unset TOKEN; history -d $(history 1)` (or just close the terminal tab).

**Checkpoint:** Token verified via the API with `success: true`, and you have it stored safely.

**Rollback:** Cloudflare → **My Profile** → **API Tokens** → find the token → **⋯** → **Roll** (regenerates) or **Delete**.

---

### Task 4: Capture the `pyquant.io` Zone ID

**Why:** The DDNS script addresses records by Zone ID, not zone name.

**Files:** None.

- [ ] **Step 1: Open zone overview**

Click-path: Cloudflare → **Websites** → click `pyquant.io`.

- [ ] **Step 2: Copy the Zone ID**

On the right sidebar (Overview page), under the **API** section, you'll see **Zone ID** with a **Copy** button. Copy the 32-character hex string. Referred to as `<ZONE_ID>` below.

**Checkpoint:** You have `<ZONE_ID>` saved alongside `<TOKEN>` from Task 3.

**Rollback:** Not applicable — this is a read-only capture.

---

### Task 5: Create DNS records in Cloudflare

**Why:** The A record must exist before Caddy requests a cert (DNS-01 challenge needs the zone to actually be live). CNAMEs for `www` and `idp` let us update only the apex via DDNS.

**Files:** None.

- [ ] **Step 1: Get current WAN IP**

On server:
```bash
ssh igor@ubuntu-server.local 'curl -s -4 --max-time 10 ifconfig.me; echo'
```
Save the IPv4 returned as `<WAN_IP>` (should be close to `184.144.56.28` unless Bell rotated it).

- [ ] **Step 2: Create A record for apex**

Click-path: Cloudflare → `pyquant.io` → **DNS** → **Records** → **Add record**:
- Type: **A**
- Name: `@` (Cloudflare shows this as `pyquant.io`)
- IPv4 address: `<WAN_IP>`
- Proxy status: **DNS only** (grey cloud — click the orange cloud to toggle off)
- TTL: **Auto**
- Click **Save**.

- [ ] **Step 3: Create CNAME for www**

**Add record**:
- Type: **CNAME**
- Name: `www`
- Target: `pyquant.io`
- Proxy status: **DNS only**
- TTL: **Auto**
- **Save**.

- [ ] **Step 4: Create CNAME for idp**

**Add record**:
- Type: **CNAME**
- Name: `idp`
- Target: `pyquant.io`
- Proxy status: **DNS only**
- TTL: **Auto**
- **Save**.

- [ ] **Step 5: Verify records resolve**

Only useful once nameservers from Task 2 have propagated. On mac:
```bash
dig +short pyquant.io @1.1.1.1       # expect <WAN_IP>
dig +short www.pyquant.io @1.1.1.1   # expect: pyquant.io.\n<WAN_IP>
dig +short idp.pyquant.io @1.1.1.1   # expect: pyquant.io.\n<WAN_IP>
```

**Checkpoint:** All three queries return `<WAN_IP>` (CNAMEs resolve through). If not, nameservers haven't propagated yet — re-check `dig NS pyquant.io @1.1.1.1` from Task 2.3.

**Rollback:** Cloudflare → DNS → Records → click each record → **Delete**.

---

## Phase 2 — Server-side config (10–15 min)

From here on, work happens over SSH: `ssh igor@ubuntu-server.local` (shortcut for `ssh igor@192.168.2.100`).

### Task 6: Back up the current Caddyfile

**Why:** Single restore point if any subsequent edit breaks Caddy parsing. The `.bak.<timestamp>` convention is already used on the server.

**Files:**
- Read: `/srv/ledgertm/Caddyfile`
- Create: `/srv/ledgertm/Caddyfile.bak.<timestamp>`

- [ ] **Step 1: Create timestamped backup**

On server:
```bash
cd /srv/ledgertm
cp Caddyfile Caddyfile.bak.$(date +%s)
ls -la Caddyfile.bak.* | tail -5
```
Expected: the new `Caddyfile.bak.<epoch>` is listed with size identical to `Caddyfile`.

**Checkpoint:** `diff Caddyfile Caddyfile.bak.$(ls -t Caddyfile.bak.* | head -1 | xargs basename | sed 's/Caddyfile.bak.//')` prints nothing (files identical).

**Rollback:** Not applicable — this is the rollback artifact.

---

### Task 7: Back up the current compose.yml

**Why:** Same reasoning as the Caddyfile. Compose changes are rarer but equally easy to fat-finger.

**Files:**
- Read: `/srv/ledgertm/compose.yml`
- Create: `/srv/ledgertm/compose.yml.bak.<timestamp>`

- [ ] **Step 1: Create timestamped backup**

On server:
```bash
cd /srv/ledgertm
cp compose.yml compose.yml.bak.$(date +%s)
ls -la compose.yml.bak.* | tail -5
```

**Checkpoint:** Backup file exists with identical contents.

**Rollback:** Not applicable — this is the rollback artifact.

---

### Task 8: Add `CLOUDFLARE_PYQUANT_API_TOKEN` to `/srv/ledgertm/.env`

**Why:** Docker Compose auto-reads `.env` in the same directory as `compose.yml` and substitutes `${VAR}` references in `compose.yml`. This is where the real secret lives.

**Files:**
- Modify: `/srv/ledgertm/.env`

- [ ] **Step 1: Append the token**

On server (replace `<TOKEN>` with the real token from Task 3):
```bash
cd /srv/ledgertm
umask 077
printf 'CLOUDFLARE_PYQUANT_API_TOKEN=<TOKEN>\n' >> .env
chmod 600 .env
tail -3 .env   # verify the token line is present (this prints it in cleartext — do this in private)
```

- [ ] **Step 2: Verify file permissions**

```bash
ls -la /srv/ledgertm/.env
```
Expected: `-rw------- 1 igor igor`.

**Checkpoint:** `.env` contains the new line with the correct value, file mode is 600.

**Rollback:**
```bash
cd /srv/ledgertm
sed -i.revert '/^CLOUDFLARE_PYQUANT_API_TOKEN=/d' .env
```

---

### Task 9: Expose the new env var to the Caddy container in `compose.yml`

**Why:** `compose.yml` uses an explicit `environment:` list (confirmed 2026-04-24), not `env_file:`, so vars must be named individually. Without this, Caddy's `{env.CLOUDFLARE_PYQUANT_API_TOKEN}` resolves to empty.

**Files:**
- Modify: `/srv/ledgertm/compose.yml` — the `environment:` block inside `services.caddy`.

- [ ] **Step 1: Apply the edit**

On server, current block (for reference):
```yaml
    environment:
      - CLOUDFLARE_LEDGERTM_API_TOKEN=${CLOUDFLARE_LEDGERTM_API_TOKEN}
```

Change it to:
```yaml
    environment:
      - CLOUDFLARE_LEDGERTM_API_TOKEN=${CLOUDFLARE_LEDGERTM_API_TOKEN}
      - CLOUDFLARE_PYQUANT_API_TOKEN=${CLOUDFLARE_PYQUANT_API_TOKEN}
```

Use `nano /srv/ledgertm/compose.yml` (or `vim`) to add the single line.

- [ ] **Step 2: Validate compose**

```bash
cd /srv/ledgertm
docker compose config > /dev/null && echo OK
```
Expected: `OK`. If it prints errors, fix indentation/quoting before proceeding.

- [ ] **Step 3: Spot-check that Compose will inject the token**

```bash
docker compose config | grep -A4 environment:
```
Expected output includes:
```
      CLOUDFLARE_LEDGERTM_API_TOKEN: <ledgertm-token-value>
      CLOUDFLARE_PYQUANT_API_TOKEN: <pyquant-token-value>
```
(Compose renders secrets in cleartext here — make sure nobody's shoulder-surfing.)

**Checkpoint:** `docker compose config` succeeds and shows both tokens in the environment block with real values.

**Rollback:**
```bash
cd /srv/ledgertm
cp compose.yml.bak.<ts> compose.yml
# (then restart caddy container in Task 11 if already rolled forward)
```

---

### Task 10: Append `pyquant.io` blocks to the Caddyfile

**Why:** Defines how Caddy routes requests for the three new hostnames and how it requests certs for them.

**Files:**
- Modify: `/srv/ledgertm/Caddyfile` — append to end of file.

- [ ] **Step 1: Append the new blocks**

On server:
```bash
cat >> /srv/ledgertm/Caddyfile <<'EOF'

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
EOF
```

- [ ] **Step 2: Validate Caddyfile syntax (without reloading)**

On server:
```bash
docker run --rm -v /srv/ledgertm/Caddyfile:/etc/caddy/Caddyfile:ro ledgertm-ledgertm-caddy caddy validate --config /etc/caddy/Caddyfile 2>&1 | tail -20
```

If the image name above doesn't exist, use the actual running image:
```bash
IMG=$(docker inspect ledgertm-caddy --format '{{.Image}}')
docker run --rm -v /srv/ledgertm/Caddyfile:/etc/caddy/Caddyfile:ro "$IMG" caddy validate --config /etc/caddy/Caddyfile 2>&1 | tail -20
```
Expected last lines: `Valid configuration`.

**Checkpoint:** `caddy validate` prints `Valid configuration`. No errors. If it complains, the issue is almost always indentation (Caddyfile is whitespace-sensitive) — compare against the heredoc above.

**Rollback:**
```bash
cd /srv/ledgertm
cp Caddyfile.bak.<ts> Caddyfile
```

---

### Task 11: Recreate the Caddy container to pick up the new env var

**Why:** `caddy reload` alone does NOT inject new env vars — they're set at container start. `docker compose up -d` with no flag recreates only containers whose spec changed (us).

**Files:** None directly; acts on the running `ledgertm-caddy` container.

- [ ] **Step 1: Bring the service up (recreate if needed)**

On server:
```bash
cd /srv/ledgertm
docker compose up -d
```
Expected output: `✔ Container ledgertm-caddy  Started` (recreated) or `Running` (if no change). On first run with the new env var, it should recreate.

- [ ] **Step 2: Verify Caddy is still listening and healthy**

```bash
docker ps --filter name=ledgertm-caddy --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
ss -tlnp 2>/dev/null | grep -E ':(80|443) '
```
Expected: container status `Up X seconds`, and host is still listening on 80/443.

- [ ] **Step 3: Watch logs for cert acquisition (2–5 min)**

```bash
docker logs -f ledgertm-caddy 2>&1 | grep -Ei 'pyquant|cert|error' &
LOG_PID=$!
sleep 180
kill $LOG_PID 2>/dev/null
```
Expected during those 3 minutes, for each of `pyquant.io`, `www.pyquant.io`, `idp.pyquant.io`:
- `obtaining certificate` → `challenge completed` → `certificate obtained successfully`

If you see repeated `failed to solve challenge` — most common causes: nameservers not propagated (Task 2), wrong token scope (Task 3), token mis-pasted (Task 8). Diagnostic:
```bash
docker exec ledgertm-caddy sh -c 'env | grep CLOUDFLARE'
```
Expected: both tokens show up with real values.

**Checkpoint:** `docker logs ledgertm-caddy | grep 'certificate obtained' | grep pyquant` shows three successful issuances (one per hostname).

**Rollback:**
```bash
cd /srv/ledgertm
cp Caddyfile.bak.<ts> Caddyfile
cp compose.yml.bak.<ts> compose.yml
docker compose up -d
```

---

## Phase 3 — DDNS for the new zone (15 min)

### Task 12: Add pyquant zone vars to `/home/igor/ddns/.env`

**Why:** The DDNS script (updated in Task 13) reads these to know which zone to update with the current WAN IP.

**Files:**
- Modify: `/home/igor/ddns/.env`

- [ ] **Step 1: Append the two vars**

On server (replace `<TOKEN>` and `<ZONE_ID>` with real values):
```bash
cd ~/ddns
umask 077
printf 'CLOUDFLARE_PYQUANT_API_TOKEN=<TOKEN>\nCLOUDFLARE_PYQUANT_ZONE_ID=<ZONE_ID>\n' >> .env
chmod 600 .env
tail -6 .env  # sanity check
```

**Checkpoint:** `.env` now has four lines total (two for ledgertm, two for pyquant), mode 600.

**Rollback:**
```bash
sed -i.revert -E '/^CLOUDFLARE_PYQUANT_(API_TOKEN|ZONE_ID)=/d' ~/ddns/.env
```

---

### Task 13: Refactor `update.sh` to loop over zones

**Why:** Current script hard-codes one zone. We want both zones updated each tick without duplicating 40 lines.

**Files:**
- Backup: `/home/igor/ddns/update.sh` → `/home/igor/ddns/update.sh.bak.<ts>`
- Replace: `/home/igor/ddns/update.sh` (new version below)

- [ ] **Step 1: Backup the existing script**

On server:
```bash
cp ~/ddns/update.sh ~/ddns/update.sh.bak.$(date +%s)
```

- [ ] **Step 2: Write the refactored script**

On server:
```bash
cat > ~/ddns/update.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
CACHE_FILE="${SCRIPT_DIR}/.last-ip"

json_get() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)" <<< "$2"; }

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found"
    exit 1
fi
# shellcheck disable=SC1090
source "$ENV_FILE"

# Each entry: "domain|zone_id_var|token_var"
ZONES=(
    "ledgertm.com|CLOUDFLARE_LEDGERTM_ZONE_ID|CLOUDFLARE_LEDGERTM_API_TOKEN"
    "pyquant.io|CLOUDFLARE_PYQUANT_ZONE_ID|CLOUDFLARE_PYQUANT_API_TOKEN"
)

CF_API="https://api.cloudflare.com/client/v4"

CURRENT_IP=$(curl -s -4 --max-time 10 ifconfig.me)
if [ -z "$CURRENT_IP" ]; then
    echo "$(date): ERROR: Could not determine public IP"
    exit 1
fi

LAST_IP=""
[ -f "$CACHE_FILE" ] && LAST_IP=$(cat "$CACHE_FILE")

if [ "$CURRENT_IP" = "$LAST_IP" ]; then
    exit 0
fi

echo "$(date): IP changed: ${LAST_IP:-none} -> ${CURRENT_IP}"

ANY_FAIL=0
for spec in "${ZONES[@]}"; do
    IFS='|' read -r DOMAIN ZID_VAR TOK_VAR <<< "$spec"
    ZONE_ID="${!ZID_VAR:-}"
    TOKEN="${!TOK_VAR:-}"
    if [ -z "$ZONE_ID" ] || [ -z "$TOKEN" ]; then
        echo "$(date): ${DOMAIN}: SKIP — ${ZID_VAR} or ${TOK_VAR} missing in .env"
        ANY_FAIL=1
        continue
    fi

    AUTH_HEADER="Authorization: Bearer ${TOKEN}"

    RECORD_RESPONSE=$(curl -s --max-time 10 \
        -H "$AUTH_HEADER" \
        -H "Content-Type: application/json" \
        "${CF_API}/zones/${ZONE_ID}/dns_records?type=A&name=${DOMAIN}")

    RECORD_ID=$(json_get "d['result'][0]['id'] if d.get('result') else ''" "$RECORD_RESPONSE" 2>/dev/null || echo "")

    if [ -z "$RECORD_ID" ]; then
        echo "$(date): ${DOMAIN}: No A record found, creating..."
        RESPONSE=$(curl -s --max-time 10 -X POST \
            -H "$AUTH_HEADER" \
            -H "Content-Type: application/json" \
            -d "{\"type\":\"A\",\"name\":\"${DOMAIN}\",\"content\":\"${CURRENT_IP}\",\"ttl\":300,\"proxied\":false}" \
            "${CF_API}/zones/${ZONE_ID}/dns_records")
    else
        RESPONSE=$(curl -s --max-time 10 -X PUT \
            -H "$AUTH_HEADER" \
            -H "Content-Type: application/json" \
            -d "{\"type\":\"A\",\"name\":\"${DOMAIN}\",\"content\":\"${CURRENT_IP}\",\"ttl\":300,\"proxied\":false}" \
            "${CF_API}/zones/${ZONE_ID}/dns_records/${RECORD_ID}")
    fi

    SUCCESS=$(json_get "d.get('success', False)" "$RESPONSE")
    if [ "$SUCCESS" = "True" ]; then
        ACTION=$( [ -z "$RECORD_ID" ] && echo "Created" || echo "Updated" )
        echo "$(date): ${ACTION} ${DOMAIN} A record -> ${CURRENT_IP}"
    else
        ERRORS=$(json_get "d.get('errors', [])" "$RESPONSE")
        echo "$(date): ERROR: ${DOMAIN}: Cloudflare API: ${ERRORS}"
        ANY_FAIL=1
    fi
done

if [ "$ANY_FAIL" -eq 0 ]; then
    echo "$CURRENT_IP" > "$CACHE_FILE"
else
    echo "$(date): At least one zone failed; .last-ip NOT updated so we retry next tick."
    exit 1
fi
EOF
chmod 700 ~/ddns/update.sh
```

Key behavioral change from the old script: `.last-ip` only advances when **all** zones succeed. If one zone fails, the next cron tick retries everything. Prevents "silent drift" where ledgertm succeeds and pyquant is forgotten.

- [ ] **Step 3: Syntax-check the script**

```bash
bash -n ~/ddns/update.sh && echo "syntax OK"
```

**Checkpoint:** Script is executable (`-rwx------`), syntax OK, backup file present.

**Rollback:**
```bash
cp ~/ddns/update.sh.bak.<ts> ~/ddns/update.sh
```

---

### Task 14: Force DDNS to run immediately, then verify

**Why:** Cron ticks every 5 min. We want to confirm the refactor works *before* walking away.

**Files:** None; exercises `~/ddns/update.sh`.

- [ ] **Step 1: Clear the cache so the script actually runs the API calls**

On server:
```bash
rm -f ~/ddns/.last-ip
```

- [ ] **Step 2: Run the script manually**

```bash
~/ddns/update.sh 2>&1 | tee -a ~/ddns/ddns.log
```

- [ ] **Step 3: Confirm both zones were touched**

Expected lines in the output:
```
<date>: IP changed: none -> <WAN_IP>
<date>: Updated ledgertm.com A record -> <WAN_IP>
<date>: Updated pyquant.io A record -> <WAN_IP>     (or "Created" on the very first run — should be "Updated" since Task 5 created the record)
```

- [ ] **Step 4: Confirm the cache was written**

```bash
cat ~/ddns/.last-ip
```
Expected: the current WAN IP (one line, no trailing garbage).

- [ ] **Step 5: Confirm the crontab is intact (no change needed)**

```bash
crontab -l | grep -i ddns
```
Expected: a line similar to `*/5 * * * * /home/igor/ddns/update.sh >> /home/igor/ddns/ddns.log 2>&1`. If the line is absent for any reason, add it:
```bash
(crontab -l 2>/dev/null; echo '*/5 * * * * /home/igor/ddns/update.sh >> /home/igor/ddns/ddns.log 2>&1') | crontab -
```

**Checkpoint:** Both zones report `Updated`, `.last-ip` has the current IP, crontab has the 5-min entry.

**Rollback:** Restore old script from Task 13.1; `rm ~/ddns/.last-ip` to force re-sync on next tick.

---

## Phase 4 — End-to-end verification (10 min)

### Task 15: DNS resolution from the public internet

**Why:** Confirms Cloudflare serves your records everywhere, not just from your own network.

**Files:** None.

- [ ] **Step 1: Query via a non-Cloudflare resolver**

On mac:
```bash
dig +short pyquant.io @8.8.8.8
dig +short www.pyquant.io @8.8.8.8
dig +short idp.pyquant.io @8.8.8.8
```
Expected: all three ultimately resolve to `<WAN_IP>` (CNAMEs may show the chain first).

**Checkpoint:** All three lookups return the correct IP.

**Rollback:** Not applicable.

---

### Task 16: TLS + HTTP behavior

**Why:** Confirms Caddy is actually terminating TLS with real Let's Encrypt certs and routing to the right backends.

**Files:** None.

- [ ] **Step 1: Check cert issuer and expiry**

On mac:
```bash
for host in pyquant.io www.pyquant.io idp.pyquant.io; do
    echo "--- $host ---"
    echo | openssl s_client -connect "$host:443" -servername "$host" 2>/dev/null \
        | openssl x509 -noout -subject -issuer -dates
done
```
Expected for each:
- `subject=CN = <host>`
- `issuer=C = US, O = Let's Encrypt, CN = R10` (or similar R10/R11/E5/E6 intermediate)
- `notAfter` ~90 days from today.

- [ ] **Step 2: Check HTTP behavior**

```bash
curl -sIL https://pyquant.io           | grep -E '^(HTTP|location|server)'
curl -sIL https://www.pyquant.io       | grep -E '^(HTTP|location|server)'
curl -sIL https://idp.pyquant.io       | grep -E '^(HTTP|location|server)'
```
Expected:
- `pyquant.io` → `HTTP/2 200` or `HTTP/2 302` (if BFF redirects unauthenticated users to /login), `server: Caddy`.
- `www.pyquant.io` → `HTTP/2 301`, `location: https://pyquant.io/`, then the final apex hop.
- `idp.pyquant.io` → `HTTP/2 200` or `HTTP/2 404` (IdP default route), `server: Caddy`.

- [ ] **Step 3: Open in a real browser**

Visit `https://pyquant.io` in Safari/Chrome. Expected: green lock, Let's Encrypt cert, the quant-platform BFF UI (whatever it currently renders for `quant.ledgertm.com`).

Visit `https://www.pyquant.io`. Expected: transparent redirect to `https://pyquant.io` (URL bar changes).

**Checkpoint:** All three hosts serve valid LE certs, all three respond with `server: Caddy`, browser shows no security warnings.

**Rollback:** If TLS is fundamentally broken, use Task 11's rollback block.

---

### Task 17: Functional smoke test against backends

**Why:** TLS can succeed while the reverse-proxy is mis-wired. Hit a known BFF/IdP endpoint to confirm actual traffic reaches them.

**Files:** None.

- [ ] **Step 1: Pick a known endpoint on each backend**

The quant-platform backends are the same ones `quant.ledgertm.com` uses. On mac:
```bash
# Replace these paths with real endpoints known to return 200 on the existing quant.ledgertm.com
# (if unsure, curl quant.ledgertm.com for the same paths first to confirm what a healthy response looks like)
curl -sI https://quant.ledgertm.com/healthz
curl -sI https://pyquant.io/healthz
curl -sI https://idp.pyquant.io/.well-known/openid-configuration
```
Expected: matching status codes on `/healthz` between `quant.ledgertm.com` and `pyquant.io`. The OIDC discovery doc on `idp.pyquant.io` should return JSON with an `issuer` field.

**Checkpoint:** At least one path returns `200` on both hostnames; responses look equivalent.

**Rollback:** If only `pyquant.io` is broken while `quant.ledgertm.com` works, the problem is Caddyfile-only — use Task 10's rollback.

---

## Phase 5 — Documentation and cleanup (5 min)

### Task 18: Update the on-server NETWORKING.md

**Why:** `/home/igor/docs/NETWORKING.md` is the canonical place the next session (or you in 3 months) will look to understand the current state. Leaving it claiming "DDNS updates only ledgertm.com" would mislead.

**Files:**
- Modify: `/home/igor/docs/NETWORKING.md`

- [ ] **Step 1: Update the DNS section**

On server, open `~/docs/NETWORKING.md` in an editor and find the DNS block. Change:

**Before:**
```
- `ledgertm.com` — managed via `CLOUDFLARE_LEDGERTM_API_TOKEN` (zone ID `a3cd858766a91611a86f494bc1b03898`)
  - `ledgertm.com` A → `184.144.56.28` (DDNS-updated)
  - `www.ledgertm.com` → `184.144.56.28` (CNAME or A to apex)
- `ivamare.com` — managed via `CLOUDFLARE_API_TOKEN` (retired from this box, but DNS still updated)
```

**After:**
```
- `ledgertm.com` — managed via `CLOUDFLARE_LEDGERTM_API_TOKEN` (zone ID `a3cd858766a91611a86f494bc1b03898`)
  - `ledgertm.com` A → current WAN IP (DDNS-updated every 5 min)
  - `www.ledgertm.com` → `ledgertm.com` (CNAME)
- `pyquant.io` — managed via `CLOUDFLARE_PYQUANT_API_TOKEN` (zone ID <ZONE_ID>)
  - `pyquant.io` A → current WAN IP (DDNS-updated every 5 min)
  - `www.pyquant.io` → `pyquant.io` (CNAME) — 301-redirects to apex via Caddy
  - `idp.pyquant.io` → `pyquant.io` (CNAME) — reverse-proxies to quant-platform IdP
- `ivamare.com` — managed via `CLOUDFLARE_API_TOKEN` (zone exists; no DDNS, no Caddy routes)
```

Also update the sentence "Updates only `ledgertm.com`" in the surrounding prose to: "Updates `ledgertm.com` and `pyquant.io`."

- [ ] **Step 2: Commit to the docs backup (if versioned)**

`~/docs/` isn't a git repo today. Optional: keep it as-is, or `git init` it for history. Out of scope for this plan.

**Checkpoint:** `grep pyquant ~/docs/NETWORKING.md` returns at least 3 lines matching the intended content.

**Rollback:** Revert the file by hand (it was appended-to, not replaced).

---

### Task 19: Update `MEMORY.md` on the mac side (optional, 2 min)

**Why:** So the next Claude Code session starts with accurate context about what's hosted.

**Files:**
- Modify: `/Users/igormusic/.claude/projects/-Users-igormusic-code-quant-platform/memory/reference_home_lab_servers.md`

- [ ] **Step 1: Add pyquant.io to the existing memory**

Append to the **"Cloudflare zones"** sentence in that memory file:
- Existing: `CLOUDFLARE_LEDGERTM_API_TOKEN` (ledgertm.com), `CLOUDFLARE_API_TOKEN` (ivamare.com — retired/no DDNS).
- After: add `, CLOUDFLARE_PYQUANT_API_TOKEN` (pyquant.io — active, dual-homes with quant.ledgertm.com 2026-04-24 → retiring quant.ledgertm.com ~2026-05-08).

**Checkpoint:** The memory file mentions pyquant.io.

**Rollback:** Revert by hand.

---

### Task 20: Checkpoint — note the retirement date for `quant.ledgertm.com`

**Why:** The design is a dual-home, not additive. Without a reminder, `quant.ledgertm.com` becomes permanent shadow infra.

**Files:** Your own calendar / task tracker.

- [ ] **Step 1: Put a reminder two weeks out**

Target retirement date: **2026-05-08** (two weeks from today).

When you get there, retiring `quant.ledgertm.com` is a ~5-min change: remove its site block from `/srv/ledgertm/Caddyfile`, delete the DNS record at Cloudflare, `docker exec ledgertm-caddy caddy reload`.

**Checkpoint:** Reminder set.

**Rollback:** Not applicable.

---

## Self-review (completed by plan author)

- **Spec coverage:**
  - Data flow → Tasks 5 (DNS), 10 (Caddyfile), 17 (smoke test).
  - DNS records (apex A, two CNAMEs, grey-cloud) → Task 5.
  - Caddyfile additions (tls_cf_pyquant + three blocks) → Task 10.
  - Secrets (.env + compose.yml env whitelist) → Tasks 8, 9.
  - DDNS loop refactor → Tasks 13, 14.
  - User-owned prereqs (CF zone, NS change, token, zone ID) → Tasks 1–4.
  - Verification (dig, curl, browser, cert issuer) → Tasks 15–17.
  - Rollback strategy (Caddyfile.bak.<ts>, <30 s revert) → per-task rollback sections; most rely on backup from Tasks 6, 7, 13.
  - Risks (token scope, NS propagation, WAN rotation, typo) → covered by Task 3.5 (token verify), Task 2.3 (NS check), Task 14 (force DDNS), Task 10.2 (caddy validate) respectively.
  - Update NETWORKING.md → Task 18.
- **Placeholder scan:** Only `<TOKEN>`, `<ZONE_ID>`, `<WAN_IP>`, `<ts>` remain. All are runtime values the user substitutes; none are TODOs hiding from the author. Commit message strings are concrete.
- **Type/name consistency:** Env var names `CLOUDFLARE_PYQUANT_API_TOKEN` and `CLOUDFLARE_PYQUANT_ZONE_ID` used identically across Tasks 8, 9, 10 (Caddyfile), 12, 13.
- **Known gap, explicitly deferred:** `/srv/ledgertm/` naming refactor and `quant.ledgertm.com` retirement — both noted as follow-ups (design Section "Open questions", Task 20).
