"""qp CLI entry point."""
from __future__ import annotations

import typer

from quantplatform import __version__

app = typer.Typer(
    name="qp",
    help="Quant Platform CLI — local stack and strategy workflows.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"qp {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show qp version and exit.",
    ),
) -> None:
    """qp — Quant Platform CLI."""
