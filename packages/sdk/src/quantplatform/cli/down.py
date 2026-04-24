"""`pq down` — stop the local stack. Data volumes are preserved by default."""
from __future__ import annotations

import subprocess

import typer
from rich.console import Console

console = Console()


def down() -> None:
    """Stop the local Quant Platform stack (docker compose down; volumes preserved)."""
    console.print("[bold]Stopping Quant Platform stack...[/bold]")
    result = subprocess.run(
        ["docker", "compose", "down"],
        check=False,
    )
    if result.returncode != 0:
        console.print("[red]docker compose down failed.[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Stack stopped.[/green] Data volumes preserved.")
