"""Unit tests for `pq e2e` — subprocess.run mocked to simulate stage results."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from quantplatform.cli.main import app


def _write_project(tmp_path: Path, name: str = "hello-world") -> Path:
    project = tmp_path / name
    project.mkdir()
    (project / "pq.toml").write_text(f"""
[project]
name = "{name}"
entry = "{name.replace('-', '_')}.strategy:main"
""")
    (project / "tests").mkdir()
    return project


def test_e2e_runs_all_stages_in_order(runner: CliRunner, tmp_path: Path) -> None:
    project = _write_project(tmp_path)

    with patch("quantplatform.cli.e2e.subprocess.run") as sub_run, \
         patch("quantplatform.cli.e2e.shutil.which", return_value="/usr/bin/pyright"):
        sub_run.return_value.returncode = 0
        import os
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["e2e", "hello-world"])
        finally:
            os.chdir(old)

    assert result.exit_code == 0, result.output
    cmds = [call.args[0] for call in sub_run.call_args_list]
    labels = [" ".join(c) for c in cmds]
    assert any("ruff check" in l for l in labels)
    assert any("ruff format" in l and "--check" in l for l in labels)
    assert any("pyright" in l for l in labels)
    assert any("pytest" in l for l in labels)
    assert any(c[:3] == ["pq", "run", "hello-world"] for c in cmds)


def test_e2e_short_circuits_on_first_fatal_failure(runner: CliRunner, tmp_path: Path) -> None:
    project = _write_project(tmp_path)

    call_index = [0]

    def side_effect(cmd, **kw):
        call_index[0] += 1
        from types import SimpleNamespace
        # Fail on first stage (ruff check)
        return SimpleNamespace(returncode=1 if call_index[0] == 1 else 0)

    with patch("quantplatform.cli.e2e.subprocess.run", side_effect=side_effect), \
         patch("quantplatform.cli.e2e.shutil.which", return_value=None):
        import os
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["e2e", "hello-world"])
        finally:
            os.chdir(old)

    assert result.exit_code == 1
    assert call_index[0] == 1  # short-circuited after first failure


def test_e2e_passes_summary_when_all_green(runner: CliRunner, tmp_path: Path) -> None:
    project = _write_project(tmp_path)
    with patch("quantplatform.cli.e2e.subprocess.run") as sub_run, \
         patch("quantplatform.cli.e2e.shutil.which", return_value=None):
        sub_run.return_value.returncode = 0
        import os
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["e2e", "hello-world"])
        finally:
            os.chdir(old)
    assert result.exit_code == 0
    assert "summary" in result.output.lower()
