"""`pq run <name>` — execute a strategy in host mode (container mode in T11)."""
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
        f"no pq.toml found in {cwd} or {cwd / (name or '<name>')}. "
        f"Run from a project directory or scaffold with `pq new strategy {name or '<name>'}`."
    )


def _read_pq_toml(project_dir: Path) -> dict:
    with open(project_dir / "pq.toml", "rb") as f:
        return tomllib.load(f)


def _git_sha(project_dir: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_dir, capture_output=True, text=True, timeout=3,
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
    return os.environ.get("QP_API_URL", "http://localhost:18000")


def run(
    name: str | None = typer.Argument(None, help="Strategy name (project directory). Defaults to cwd project."),
    as_of: str | None = typer.Option(None, "--as-of", help="Run date YYYY-MM-DD (default: today)"),
    debug: bool = typer.Option(False, "--debug", help="Start strategy under debugpy; wait for IDE attach"),
    container: bool = typer.Option(False, "--container", help="Run inside worker container (M3-T11)"),
) -> None:
    """Execute a strategy locally."""
    if container:
        console.print("[yellow]--container mode lands in M3-T11[/yellow]")
        raise typer.Exit(code=3)

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

    # Spawn strategy subprocess
    entry_module = entry.split(":")[0]  # "pkg.mod:main" -> "pkg.mod"
    env = {
        **os.environ,
        "QP_STRATEGY_ID": strategy_id,
        "QP_AS_OF": as_of_str,
    }

    if debug:
        cmd = ["uv", "run", "python", "-m", "debugpy", "--listen", "5678",
               "--wait-for-client", "-m", entry_module]
        console.print("[yellow]Waiting for debugger to attach on localhost:5678...[/yellow]")
    else:
        cmd = ["uv", "run", "python", "-m", entry_module]

    console.print(f"[bold]Running strategy:[/bold] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_dir, env=env)
    if result.returncode != 0:
        console.print(f"[red]strategy exited with code {result.returncode}[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Strategy completed successfully.[/green]")
