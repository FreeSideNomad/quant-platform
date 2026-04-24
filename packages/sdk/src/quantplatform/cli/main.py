"""qp CLI entry point."""
from __future__ import annotations

import typer

from quantplatform import __version__
from quantplatform.cli.doctor import doctor as doctor_command
from quantplatform.cli.down import down as down_command
from quantplatform.cli.up import up as up_command

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


app.command(name="up", help="Start the local Quant Platform stack.")(up_command)
app.command(name="down", help="Stop the local Quant Platform stack (volumes preserved).")(down_command)
app.command(name="doctor", help="Verify Docker, uv, Python, and free ports.")(doctor_command)
