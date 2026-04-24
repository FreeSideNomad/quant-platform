"""Unit tests for `pq new strategy`."""
from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quantplatform.cli.main import app


def test_new_strategy_scaffolds_vol_har(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "hello-world"
    result = runner.invoke(app, ["new", "strategy", "hello-world", "--dir", str(target)])
    assert result.exit_code == 0, result.output

    # Files expected
    assert (target / "pq.toml").is_file()
    assert (target / "pyproject.toml").is_file()
    assert (target / "README.md").is_file()
    assert (target / "src" / "hello-world" / "__init__.py").is_file() or \
           (target / "src" / "hello_world" / "__init__.py").is_file()
    # strategy.py under src/<name>/ — accept either hyphen or underscore dir
    strategy_files = list(target.glob("src/*/strategy.py"))
    assert len(strategy_files) == 1
    # strategy.py parses as valid Python
    ast.parse(strategy_files[0].read_text())
    # tests/test_strategy.py parses
    ast.parse((target / "tests" / "test_strategy.py").read_text())
    # pq.toml is valid TOML with name = "hello-world"
    with open(target / "pq.toml", "rb") as f:
        doc = tomllib.load(f)
    assert doc["project"]["name"] == "hello-world"


def test_new_strategy_rejects_non_empty_dir_without_force(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    (target / "preexisting_file.txt").write_text("hi")
    result = runner.invoke(app, ["new", "strategy", "anything", "--dir", str(target)])
    assert result.exit_code == 1
    assert "not empty" in result.output


def test_new_strategy_overwrites_with_force(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    (target / "stale.txt").write_text("stale")
    result = runner.invoke(
        app, ["new", "strategy", "hello-world", "--dir", str(target), "--force"]
    )
    assert result.exit_code == 0, result.output
    assert (target / "pq.toml").is_file()


def test_new_strategy_rejects_invalid_name(runner: CliRunner, tmp_path: Path) -> None:
    target = tmp_path / "bad"
    # Starts with digit
    result = runner.invoke(app, ["new", "strategy", "3bad", "--dir", str(target)])
    assert result.exit_code == 2
    assert "invalid name" in result.output


def test_new_strategy_returns_template_not_yet_implemented(
    runner: CliRunner, tmp_path: Path
) -> None:
    target = tmp_path / "hello-returns"
    result = runner.invoke(
        app, ["new", "strategy", "hello-returns", "--template", "returns", "--dir", str(target)]
    )
    assert result.exit_code == 3
    assert "M4" in result.output
