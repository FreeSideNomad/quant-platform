"""`pq down` — stop the local stack. Data volumes are preserved by default."""
from __future__ import annotations

import subprocess

import typer
from rich.console import Console

from quantplatform.cli._pqhome import require_platform_dir

console = Console()


def down() -> None:
    """Stop the local Quant Platform stack (docker compose down; volumes preserved)."""
    try:
        platform_dir = require_platform_dir()
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Stopping Quant Platform stack[/bold] (from {platform_dir})...")
    result = subprocess.run(
        ["docker", "compose", "down"],
        cwd=platform_dir,
        check=False,
    )
    if result.returncode != 0:
        console.print("[red]docker compose down failed.[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Stack stopped.[/green] Data volumes preserved.")
