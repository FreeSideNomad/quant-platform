"""`pq run` — execute a strategy in host mode (container mode via --container).

`pq run` defaults to the project rooted at the current working directory
(detected by `pq.toml`). An explicit `pq run <name>` resolves to `./<name>/`
for convenience, but the canonical workflow is `cd <project> && pq run`.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from datetime import date
from pathlib import Path

import httpx
import typer
import xxhash
from rich.console import Console

console = Console()


# Canonical platform endpoints injected into the strategy subprocess so the
# SDK can find Postgres / MinIO / MLflow without the user having to know
# what `pq up` exposes. All keys are PQ_-prefixed to avoid clashing with
# any DATABASE_URL / S3_* / MLFLOW_TRACKING_URI the user may have in their
# shell for unrelated work. Ports match the spec-codified host bindings.
PLATFORM_ENV = {
    "PQ_DATABASE_URL": "postgresql://qp:qp@localhost:15432/qp",
    "PQ_S3_ENDPOINT_URL": "http://localhost:19000",
    "PQ_S3_ACCESS_KEY": "minioadmin",
    "PQ_S3_SECRET_KEY": "minioadmin",
    "PQ_MLFLOW_TRACKING_URI": "http://localhost:15000",
    "PQ_API_URL": "http://localhost:18000",
}


def _resolve_project_dir(name: str | None) -> Path:
    """Find the project dir by looking for pq.toml.

    Order: (1) cwd if it has pq.toml; (2) cwd/<name> if that has pq.toml.
    """
    cwd = Path.cwd()
    if (cwd / "pq.toml").is_file():
        return cwd
    if name:
        candidate = cwd / name
        if (candidate / "pq.toml").is_file():
            return candidate
    raise FileNotFoundError(
        f"no pq.toml found in {cwd}"
        + (f" or {cwd / name}" if name else "")
        + ". Run from inside a project directory, or scaffold one with `pq new <project>`."
    )


def _read_pq_toml(project_dir: Path) -> dict:
    with open(project_dir / "pq.toml", "rb") as f:
        return tomllib.load(f)


def _git_sha(project_dir: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _uv_lock_hash(project_dir: Path) -> str:
    lock = project_dir / "uv.lock"
    if not lock.is_file():
        return "unknown"
    return xxhash.xxh64(lock.read_bytes()).hexdigest()


def _api_base_url() -> str:
    return os.environ.get("PQ_API_URL", PLATFORM_ENV["PQ_API_URL"])


def _find_compose_dir(project_dir: Path) -> Path:
    """Locate the quant-platform repo root for `pq run --container`.

    Reads from `~/.pq/config.toml` (set by `pq init`). The `project_dir`
    arg is unused but kept for backward compatibility with the historical
    walk-up call site; if the user hasn't run `pq init`, raises with a
    helpful message.
    """
    from quantplatform.cli._pqhome import require_platform_dir

    del project_dir  # no longer used; configured location is authoritative
    return require_platform_dir()


def _run_container_mode(
    *,
    project_dir: Path,
    strategy_id: str,
    entry_module: str,
    as_of: str,
    debug: bool,
) -> int:
    """Run the strategy inside the worker container via docker compose run."""
    inner_cmd: list[str]
    if debug:
        inner_cmd = [
            "python",
            "-m",
            "debugpy",
            "--listen",
            "0.0.0.0:5678",
            "--wait-for-client",
            "-m",
            entry_module,
        ]
        console.print(
            "[yellow]Worker will wait for debugger on localhost:5678; attach your IDE now.[/yellow]"
        )
    else:
        inner_cmd = ["python", "-m", entry_module]

    compose_dir = _find_compose_dir(project_dir)

    cmd = [
        "docker",
        "compose",
        "--profile",
        "worker",
        "run",
        "--rm",
        "--service-ports",
        "--volume",
        f"{project_dir.resolve()}:/workspace:ro",
        "--workdir",
        "/workspace",
        "worker",
        *inner_cmd,
    ]
    console.print(f"[bold]Container exec:[/bold] {' '.join(cmd)}")

    # Container picks up its own PQ_* via docker-compose env. We only need
    # to forward the per-run identifiers here.
    env = {
        **os.environ,
        "PQ_STRATEGY_ID": strategy_id,
        "PQ_AS_OF": as_of,
    }
    result = subprocess.run(cmd, cwd=compose_dir, env=env)
    return result.returncode


def run(
    name: str | None = typer.Argument(
        None,
        help="Optional project name (./<name>/). Default: cwd if it has pq.toml.",
    ),
    as_of: str | None = typer.Option(None, "--as-of", help="Run date YYYY-MM-DD (default: today)"),
    debug: bool = typer.Option(
        False, "--debug", help="Start strategy under debugpy; wait for IDE attach"
    ),
    container: bool = typer.Option(
        False, "--container", help="Run inside worker container via docker compose"
    ),
) -> None:
    """Execute a strategy locally."""
    try:
        project_dir = _resolve_project_dir(name)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    pq_toml = _read_pq_toml(project_dir)
    try:
        strategy_name = pq_toml["project"]["name"]
        entry = pq_toml["project"]["entry"]
    except KeyError as e:
        console.print(f"[red]pq.toml missing required field: {e}[/red]")
        raise typer.Exit(code=1)
    thresholds = pq_toml.get("thresholds", {})

    as_of_str = as_of or date.today().isoformat()

    # Upsert strategy
    console.print(f"[bold]Upserting strategy {strategy_name!r}...[/bold]")
    try:
        r = httpx.post(
            f"{_api_base_url()}/strategies",
            json={
                "name": strategy_name,
                "entry_point": entry,
                "thresholds": thresholds,
                "git_sha": _git_sha(project_dir),
                "uv_lock_hash": _uv_lock_hash(project_dir),
            },
            timeout=10,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        console.print(f"[red]strategy upsert failed: {e}[/red]")
        console.print("[yellow]Is the stack running? Try `pq up`.[/yellow]")
        raise typer.Exit(code=2)

    upsert = r.json()
    strategy_id = upsert["strategy_id"]
    action = "created" if upsert["created"] else "updated"
    console.print(f"[green]Strategy {action}: {strategy_name} ({strategy_id[:8]})[/green]")

    entry_module = entry.split(":")[0]  # "pkg.mod:main" -> "pkg.mod"

    if container:
        console.print(f"[bold]Running {strategy_name!r} in container mode...[/bold]")
        try:
            rc = _run_container_mode(
                project_dir=project_dir,
                strategy_id=strategy_id,
                entry_module=entry_module,
                as_of=as_of_str,
                debug=debug,
            )
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1)
        if rc != 0:
            console.print(f"[red]container exited with code {rc}[/red]")
            raise typer.Exit(code=rc)
        console.print("[green]Strategy completed successfully (container).[/green]")
        return

    # Host mode: run the strategy via `uv run` in the user's project venv —
    # standard isolated Python-project workflow. The project's pyproject.toml
    # declares `quantplatform` as a dep; how it resolves (PyPI / git / path)
    # is the user's choice recorded there.
    #
    # Inject canonical platform endpoints (PQ_*) so the SDK can reach
    # Postgres / MinIO / MLflow without the user setting env. PQ_-prefixed
    # to avoid clashing with any DATABASE_URL / S3_* the user has in their
    # shell for unrelated work. The user's own PQ_* overrides — useful if
    # they're targeting a non-default port via custom docker-compose.
    env = {
        **PLATFORM_ENV,
        **os.environ,
        "PQ_STRATEGY_ID": strategy_id,
        "PQ_AS_OF": as_of_str,
    }

    if debug:
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "debugpy",
            "--listen",
            "5678",
            "--wait-for-client",
            "-m",
            entry_module,
        ]
        console.print("[yellow]Waiting for debugger to attach on localhost:5678...[/yellow]")
    else:
        cmd = ["uv", "run", "python", "-m", entry_module]

    console.print(f"[bold]Running strategy:[/bold] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_dir, env=env)
    if result.returncode != 0:
        console.print(f"[red]strategy exited with code {result.returncode}[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Strategy completed successfully.[/green]")
