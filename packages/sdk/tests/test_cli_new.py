"""Unit tests for `pq new`."""
from __future__ import annotations

import ast
import tomllib
from pathlib import Path

from typer.testing import CliRunner

from quantplatform.cli.main import app


def test_new_scaffolds_hello_world(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "hello-world"
    result = runner.invoke(app, ["new", "hello-world", "--dir", str(target)])
    assert result.exit_code == 0, result.output

    assert (target / "pq.toml").is_file()
    assert (target / "pyproject.toml").is_file()
    assert (target / "README.md").is_file()
    assert (target / "src" / "hello-world" / "__init__.py").is_file() or \
           (target / "src" / "hello_world" / "__init__.py").is_file()
    strategy_files = list(target.glob("src/*/strategy.py"))
    assert len(strategy_files) == 1
    ast.parse(strategy_files[0].read_text())
    ast.parse((target / "tests" / "test_strategy.py").read_text())
    with open(target / "pq.toml", "rb") as f:
        doc = tomllib.load(f)
    assert doc["project"]["name"] == "hello-world"


def test_new_default_template_is_hello_world(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`pq new <name>` with no --template defaults to hello-world."""
    target = tmp_path / "default-template"
    result = runner.invoke(app, ["new", "default-template", "--dir", str(target)])
    assert result.exit_code == 0, result.output
    assert (target / "pq.toml").is_file()


def test_new_rejects_non_empty_dir_without_force(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    (target / "preexisting_file.txt").write_text("hi")
    result = runner.invoke(app, ["new", "anything", "--dir", str(target)])
    assert result.exit_code == 1
    assert "not empty" in result.output


def test_new_overwrites_with_force(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    (target / "stale.txt").write_text("stale")
    result = runner.invoke(
        app, ["new", "hello-world", "--dir", str(target), "--force"]
    )
    assert result.exit_code == 0, result.output
    assert (target / "pq.toml").is_file()


def test_new_rejects_invalid_name(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "bad"
    result = runner.invoke(app, ["new", "3bad", "--dir", str(target)])
    assert result.exit_code == 2
    assert "invalid name" in result.output


def test_new_returns_template_not_yet_implemented(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "hello-returns"
    result = runner.invoke(
        app, ["new", "hello-returns", "--template", "returns", "--dir", str(target)]
    )
    assert result.exit_code == 3
    assert "M4" in result.output


def test_new_unknown_template_lists_choices(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "x"
    result = runner.invoke(
        app, ["new", "x", "--template", "no-such-thing", "--dir", str(target)]
    )
    assert result.exit_code == 2
    assert "hello-world" in result.output
