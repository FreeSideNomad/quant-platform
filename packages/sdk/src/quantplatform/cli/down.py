"""`pq down` — stop the local stack. Data volumes are preserved by default."""
from __future__ import annotations

import subprocess

import typer
from rich.console import Console

from quantplatform.cli._pqhome import require_platform_dir

console = Console()


def down(
    volumes: bool = typer.Option(
        False,
        "--volumes",
        "-v",
        help=(
            "Also remove the qp-postgres-data and qp-minio-data volumes. "
            "DESTROYS all local strategy / run / lineage / MLflow state. "
            "Required when crossing migration baselines or major MLflow version upgrades."
        ),
    ),
) -> None:
    """Stop the local Quant Platform stack.

    By default, data volumes are preserved so the next `pq up` resumes
    with all strategies, runs, lineage, MLflow runs, and MinIO objects
    intact. Pass `-v` / `--volumes` to additionally wipe the volumes —
    needed for fresh installs or when an upgrade requires a clean
    schema baseline (e.g. v0.3.x → v0.4.0 collapsed migrations + MLflow
    2.x → 3.x backend-store schema).
    """
    try:
        platform_dir = require_platform_dir()
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    cmd = ["docker", "compose", "down"]
    if volumes:
        cmd.append("-v")

    action = "Stopping + wiping volumes" if volumes else "Stopping"
    console.print(f"[bold]{action} the Quant Platform stack[/bold] (from {platform_dir})...")
    result = subprocess.run(cmd, cwd=platform_dir, check=False)
    if result.returncode != 0:
        console.print("[red]docker compose down failed.[/red]")
        raise typer.Exit(code=result.returncode)
    if volumes:
        console.print("[green]Stack stopped.[/green] Volumes wiped — next `pq up` is a fresh install.")
    else:
        console.print("[green]Stack stopped.[/green] Data volumes preserved.")
