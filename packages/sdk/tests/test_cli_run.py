"""Unit tests for `pq run` — mocks httpx and subprocess."""
from __future__ import annotations

import os
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

[thresholds]
pbo_max = 0.5
""")
    return project


def test_pq_run_upserts_strategy_and_spawns_subprocess(runner: CliRunner, tmp_path: Path) -> None:
    _write_project(tmp_path, "hello-world")

    with patch("quantplatform.cli.run.httpx.post") as post, \
         patch("quantplatform.cli.run.subprocess.run") as sub_run, \
         patch("quantplatform.cli.run._git_sha", return_value="abc123"), \
         patch("quantplatform.cli.run._uv_lock_hash", return_value="hashxyz"):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "strategy_id": "00000000-0000-0000-0000-000000000001",
            "created": True,
        }
        post.return_value.raise_for_status.return_value = None
        sub_run.return_value.returncode = 0

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["run", "hello-world"])
        finally:
            os.chdir(old_cwd)

    assert result.exit_code == 0, result.output
    post.assert_called_once()
    # The strategy upsert body
    body = post.call_args.kwargs["json"]
    assert body["name"] == "hello-world"
    assert body["entry_point"] == "hello_world.strategy:main"
    assert body["thresholds"] == {"pbo_max": 0.5}

    sub_run.assert_called_once()
    cmd = sub_run.call_args.args[0]
    assert cmd[:3] == ["uv", "run", "python"]
    assert "-m" in cmd
    assert "hello_world.strategy" in cmd

    env = sub_run.call_args.kwargs["env"]
    assert env["QP_STRATEGY_ID"] == "00000000-0000-0000-0000-000000000001"
    assert "QP_AS_OF" in env


def test_pq_run_fails_if_no_pq_toml(runner: CliRunner, tmp_path: Path) -> None:
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["run", "nonexistent"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 1
    assert "no pq.toml" in result.output


def test_pq_run_propagates_subprocess_exit_code(runner: CliRunner, tmp_path: Path) -> None:
    _write_project(tmp_path, "fails-here")

    with patch("quantplatform.cli.run.httpx.post") as post, \
         patch("quantplatform.cli.run.subprocess.run") as sub_run, \
         patch("quantplatform.cli.run._git_sha", return_value="abc123"), \
         patch("quantplatform.cli.run._uv_lock_hash", return_value="hashxyz"):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "strategy_id": "00000000-0000-0000-0000-000000000001",
            "created": True,
        }
        post.return_value.raise_for_status.return_value = None
        sub_run.return_value.returncode = 42

        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["run", "fails-here"])
        finally:
            os.chdir(old_cwd)

    assert result.exit_code == 42


def test_pq_run_container_flag_not_implemented(runner: CliRunner, tmp_path: Path) -> None:
    _write_project(tmp_path)
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = runner.invoke(app, ["run", "hello-world", "--container"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 3
    assert "M3-T11" in result.output


def test_pq_run_debug_adds_debugpy_to_cmd(runner: CliRunner, tmp_path: Path) -> None:
    _write_project(tmp_path, "dbg-strategy")
    with patch("quantplatform.cli.run.httpx.post") as post, \
         patch("quantplatform.cli.run.subprocess.run") as sub_run, \
         patch("quantplatform.cli.run._git_sha", return_value="abc123"), \
         patch("quantplatform.cli.run._uv_lock_hash", return_value="hashxyz"):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"strategy_id": "00000000-0000-0000-0000-000000000001", "created": False}
        post.return_value.raise_for_status.return_value = None
        sub_run.return_value.returncode = 0
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["run", "dbg-strategy", "--debug"])
        finally:
            os.chdir(old_cwd)
    cmd = sub_run.call_args.args[0]
    assert "debugpy" in cmd
    assert "5678" in cmd
