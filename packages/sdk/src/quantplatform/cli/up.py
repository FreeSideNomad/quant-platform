"""`pq up` — start the local stack via docker compose."""
from __future__ import annotations

import subprocess

import typer
from rich.console import Console

from quantplatform.cli._pqhome import require_platform_dir

console = Console()


_KNOWN_PQ_CONTAINERS = (
    "pq-postgres",
    "pq-minio",
    "pq-minio-init",
    "pq-mlflow",
    "pq-mock-oidc",
    "pq-migrations",
    "pq-api",
    "pq-ui",
    "pq-worker",
)


def _clean_stale_pq_containers() -> None:
    """Remove any stopped pq-* containers from prior clones before starting.

    The compose file pins global container_name values (pq-postgres etc.).
    If the user has a second clone that also brought up the stack at some
    point, those containers linger and the name is taken. Nuke any stopped
    one whose name matches; leave running ones alone (they'll just be
    reused by compose, or conflict-error if from a different project).
    """
    result = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=pq-", "--format", "{{.Names}}\t{{.State}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return
    to_remove = []
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        name, state = line.split("\t", 1)
        name = name.strip()
        state = state.strip().lower()
        # Only clean stopped containers matching our known set — leaves
        # running ones alone so we don't stomp on a second live stack.
        if name in _KNOWN_PQ_CONTAINERS and state in {"exited", "created", "dead"}:
            to_remove.append(name)
    if to_remove:
        subprocess.run(
            ["docker", "rm", "-f", *to_remove],
            capture_output=True,
            check=False,
        )


def up(
    no_build: bool = typer.Option(
        False,
        "--no-build",
        help="Skip rebuilding images (faster, but code/migration changes won't land).",
    ),
) -> None:
    """Start the local Quant Platform stack.

    Runs `docker compose up -d --build` by default so that source changes
    (api, UI, migrations) land without a manual rebuild step. Pass
    `--no-build` when you know nothing changed and want a faster boot.

    Also sweeps stopped `pq-*` orphan containers before starting — these
    can linger when a second clone of the platform repo brought up the
    stack at some point, and the pinned container_name values then
    conflict on boot.
    """
    try:
        platform_dir = require_platform_dir()
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    _clean_stale_pq_containers()
    cmd = ["docker", "compose", "up", "-d"]
    if not no_build:
        cmd.append("--build")
    console.print(f"[bold]Starting Quant Platform stack[/bold] (from {platform_dir})...")
    result = subprocess.run(cmd, cwd=platform_dir, check=False)
    if result.returncode != 0:
        console.print("[red]docker compose up failed.[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Stack started.[/green] UI at http://localhost:15173")
