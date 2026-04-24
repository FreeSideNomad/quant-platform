# Installing the `pq` CLI

## Prerequisites

- macOS or Linux (Windows: use WSL2)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or equivalent (Docker Engine + Compose v2)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`

## M3 install path (clone-based)

Until the hosted install endpoint at `https://quant.ledgertm.com/install.sh` is live (M4/M5) and ultimately `https://get.pyquant.io/install.sh` (M8), the platform installs from a clone:

```bash
git clone git@github.com:FreeSideNomad/quant-platform.git
cd quant-platform
uv tool install ./packages/sdk
pq --version           # → pq 0.1.0
```

`uv tool install ./packages/sdk` puts `pq` on `$PATH` (typically `~/.local/bin/pq`). Subsequent updates:

```bash
cd quant-platform && git pull
uv tool upgrade quantplatform   # or uv tool install ./packages/sdk --force
```

## Quickstart after install

```bash
# From inside the quant-platform repo:
pq doctor              # checks Docker, compose, Python, port availability
pq up                  # starts the local stack (postgres, minio, mlflow, api, ui, mock-oidc)
pq new strategy hello-world
cd hello-world
pq run hello-world     # trains + logs to MLflow (no promotion gate in M3)
```

Open http://localhost:15000 for MLflow, http://localhost:15173 for the platform UI placeholder, http://localhost:19001 for the MinIO console (user/pass: `minioadmin` / `minioadmin`).

## Staging install (M4/M5, planned)

```bash
curl -sSfL https://quant.ledgertm.com/install.sh | sh
```

Shell wrapper installs uv then `uv tool install git+https://github.com/FreeSideNomad/quant-platform.git#subdirectory=packages/sdk`. Hosted on ubuntu-server behind Caddy (see `docs/superpowers/specs/2026-04-24-pyquant-io-hosting-design.md` and the runbook plan).

## Target install (M8, planned)

```bash
curl -sSfL https://get.pyquant.io/install.sh | sh
```

M8 publishes `quantplatform` to PyPI, so post-M8 the wrapper collapses to `uv tool install quantplatform`. Homebrew tap deferred to v2.
