"""`pq up` — start the local stack via docker compose."""
from __future__ import annotations

import subprocess

import typer
from rich.console import Console

console = Console()


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
    """
    cmd = ["docker", "compose", "up", "-d"]
    if not no_build:
        cmd.append("--build")
    console.print("[bold]Starting Quant Platform stack...[/bold]")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        console.print("[red]docker compose up failed.[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Stack started.[/green] UI at http://localhost:15173")
