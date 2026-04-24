"""`pq e2e` — pre-push hook: lint + type-check + unit tests + container run."""
from __future__ import annotations

import shutil
import subprocess
import time
import tomllib
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from quantplatform.cli.run import _resolve_project_dir

console = Console()


def e2e(
    name: str | None = typer.Argument(None, help="Strategy name; defaults to cwd project."),
) -> None:
    """Run the full pre-push battery for a strategy project."""
    try:
        project_dir = _resolve_project_dir(name)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    with open(project_dir / "pq.toml", "rb") as f:
        pq = tomllib.load(f)
    strategy_name = pq["project"]["name"]

    stages: list[tuple[str, list[str], bool]] = []  # (label, cmd, fatal)
    stages.append(("ruff check", ["uv", "run", "ruff", "check", "."], True))
    stages.append(("ruff format", ["uv", "run", "ruff", "format", "--check", "."], True))
    if shutil.which("pyright") or (project_dir / "pyproject.toml").exists():
        stages.append(("pyright", ["uv", "run", "pyright"], False))
    if (project_dir / "tests").is_dir():
        stages.append(("pytest", ["uv", "run", "pytest", "tests/"], True))
    stages.append(("pq run --container", ["pq", "run", strategy_name, "--container"], True))

    results: list[tuple[str, bool, float]] = []
    t_start = time.time()

    for label, cmd, fatal in stages:
        stage_start = time.time()
        console.print(f"[bold]▶ {label}[/bold]  ({' '.join(cmd)})")
        result = subprocess.run(cmd, cwd=project_dir)
        elapsed = time.time() - stage_start
        passed = result.returncode == 0
        results.append((label, passed, elapsed))
        if not passed and fatal:
            console.print(f"[red]✗ {label} failed (exit {result.returncode})[/red]")
            _print_summary(results, time.time() - t_start)
            raise typer.Exit(code=result.returncode)

    total = time.time() - t_start
    _print_summary(results, total)
    if any(not p for _, p, _ in results):
        raise typer.Exit(code=1)


def _print_summary(results: list[tuple[str, bool, float]], total: float) -> None:
    table = Table(title=f"pq e2e summary (total: {total:.1f}s)")
    table.add_column("Stage")
    table.add_column("Result", justify="center")
    table.add_column("Time", justify="right")
    for label, passed, elapsed in results:
        mark = "[green]✓[/green]" if passed else "[red]✗[/red]"
        table.add_row(label, mark, f"{elapsed:.1f}s")
    console.print(table)
    if total > 90:
        console.print(f"[yellow]⚠ total {total:.1f}s exceeds the 90s budget[/yellow]")
