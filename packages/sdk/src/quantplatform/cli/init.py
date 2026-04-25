"""`pq init [<path>]` — record the platform repo root in `~/.pq/config.toml`.

Future `pq up` / `pq down` / `pq run --container` reads from there so they
work from any cwd. Run once after `uv tool install ./packages/sdk`.
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from quantplatform.cli._pqhome import (
    CONFIG_PATH,
    PQ_HOME,
    ensure_home,
    load_config,
    save_config,
)

console = Console()


def init(
    path: Path | None = typer.Argument(
        None,
        help="Path to the quant-platform repo root (defaults to current directory).",
    ),
) -> None:
    """Configure `~/.pq/config.toml` with the platform repo location."""
    target = (path or Path.cwd()).expanduser().resolve()
    compose = target / "docker-compose.yml"
    if not compose.is_file():
        console.print(
            f"[red]no docker-compose.yml at {target}.[/red] "
            f"Run from the quant-platform repo root or pass an explicit path."
        )
        raise typer.Exit(code=1)

    # Cheap sanity check that this is OUR compose, not some other project's:
    # look for the canonical pq-postgres container_name.
    body = compose.read_text(errors="ignore")
    if "container_name: pq-postgres" not in body:
        console.print(
            f"[red]{compose} doesn't look like the quant-platform docker-compose "
            f"(no `container_name: pq-postgres`).[/red] Refusing to record."
        )
        raise typer.Exit(code=2)

    ensure_home()
    cfg = load_config()
    cfg.setdefault("platform", {})["dir"] = str(target)
    save_config(cfg)

    console.print(f"[green]Recorded[/green] platform dir → [bold]{target}[/bold]")
    console.print(f"  pq home: [bold]{PQ_HOME}[/bold]")
    console.print(f"  config:  [bold]{CONFIG_PATH}[/bold]")
    console.print(
        "Future [bold]pq up[/bold] / [bold]pq down[/bold] / [bold]pq run --container[/bold] "
        "will use this path regardless of cwd."
    )
