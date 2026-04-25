"""pq CLI entry point."""
from __future__ import annotations

import typer

from quantplatform import __version__
from quantplatform.cli.doctor import doctor as doctor_command
from quantplatform.cli.down import down as down_command
from quantplatform.cli.e2e import e2e as e2e_command
from quantplatform.cli.init import init as init_command
from quantplatform.cli.new_strategy import new_app
from quantplatform.cli.run import run as run_command
from quantplatform.cli.up import up as up_command

app = typer.Typer(
    name="pq",
    help="Quant Platform CLI — local stack and strategy workflows.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pq {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show pq version and exit.",
    ),
) -> None:
    """pq — Quant Platform CLI."""


app.command(name="init", help="Record the platform repo path in ~/.pq/config.toml.")(init_command)
app.command(name="up", help="Start the local Quant Platform stack.")(up_command)
app.command(name="down", help="Stop the local Quant Platform stack (volumes preserved).")(down_command)
app.command(name="doctor", help="Verify Docker, uv, Python, and free ports.")(doctor_command)
app.command(name="run", help="Execute a strategy locally.")(run_command)
app.command(name="e2e", help="Pre-push: lint + type-check + unit tests + container run.")(e2e_command)
app.add_typer(new_app, name="new", help="Scaffold new projects.")
