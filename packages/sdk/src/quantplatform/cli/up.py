"""`qp up` — start the local stack via docker compose."""
from __future__ import annotations

import subprocess

import typer
from rich.console import Console

console = Console()


def up() -> None:
    """Start the local Quant Platform stack (docker compose up -d)."""
    console.print("[bold]Starting Quant Platform stack...[/bold]")
    result = subprocess.run(
        ["docker", "compose", "up", "-d"],
        check=False,
    )
    if result.returncode != 0:
        console.print("[red]docker compose up failed.[/red]")
        raise typer.Exit(code=result.returncode)
    console.print("[green]Stack started.[/green] UI at http://localhost:15173")
