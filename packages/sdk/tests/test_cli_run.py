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
    # pq run uses `uv run python -m <entry>` inside the user's project venv —
    # standard Python-project workflow, isolation preserved.
    assert cmd[:3] == ["uv", "run", "python"]
    assert "-m" in cmd
    assert "hello_world.strategy" in cmd

    env = sub_run.call_args.kwargs["env"]
    assert env["PQ_STRATEGY_ID"] == "00000000-0000-0000-0000-000000000001"
    assert "PQ_AS_OF" in env
    # Canonical platform endpoints injected so SDK can reach Postgres / MinIO / MLflow
    # without the user setting any env. PQ_-prefixed to avoid clash with the user's shell.
    assert env["PQ_DATABASE_URL"].startswith("postgresql://")
    assert env["PQ_S3_ENDPOINT_URL"].startswith("http://")
    assert env["PQ_MLFLOW_TRACKING_URI"].startswith("http://")
    # MLflow's S3 artifact store + boto3 read these directly — they can't
    # be PQ_-renamed. Force-pinned to MinIO so a strategy run never talks
    # to real AWS using day-job credentials.
    assert env["AWS_ACCESS_KEY_ID"] == "minioadmin"
    assert env["AWS_SECRET_ACCESS_KEY"] == "minioadmin"
    assert env["MLFLOW_S3_ENDPOINT_URL"] == "http://localhost:19000"


def test_pq_run_no_args_uses_cwd_project(runner: CliRunner, tmp_path: Path) -> None:
    """`pq run` with no positional arg resolves to cwd if it has pq.toml."""
    project = _write_project(tmp_path, "cwd-project")

    with patch("quantplatform.cli.run.httpx.post") as post, \
         patch("quantplatform.cli.run.subprocess.run") as sub_run, \
         patch("quantplatform.cli.run._git_sha", return_value="abc"), \
         patch("quantplatform.cli.run._uv_lock_hash", return_value="x"):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            "strategy_id": "00000000-0000-0000-0000-000000000002",
            "created": True,
        }
        post.return_value.raise_for_status.return_value = None
        sub_run.return_value.returncode = 0

        old = os.getcwd()
        os.chdir(project)
        try:
            result = runner.invoke(app, ["run"])
        finally:
            os.chdir(old)

    assert result.exit_code == 0, result.output
    body = post.call_args.kwargs["json"]
    assert body["name"] == "cwd-project"


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


def test_pq_run_container_mode_invokes_docker_compose_run(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _write_project(tmp_path, "container-strat")
    # _find_compose_dir now reads from ~/.pq/config.toml via require_platform_dir.
    # Mock that to return tmp_path so the test is hermetic.
    monkeypatch.setattr(
        "quantplatform.cli.run._find_compose_dir",
        lambda project_dir: tmp_path,
    )

    with patch("quantplatform.cli.run.httpx.post") as post, \
         patch("quantplatform.cli.run.subprocess.run") as sub_run, \
         patch("quantplatform.cli.run._git_sha", return_value="abc123"), \
         patch("quantplatform.cli.run._uv_lock_hash", return_value="deadbeef"):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"strategy_id": "00000000-0000-0000-0000-000000000001", "created": True}
        post.return_value.raise_for_status.return_value = None
        sub_run.return_value.returncode = 0

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["run", "container-strat", "--container"])
        finally:
            os.chdir(old)

    assert result.exit_code == 0, result.output
    cmd = sub_run.call_args.args[0]
    assert cmd[:4] == ["docker", "compose", "--profile", "worker"]
    assert "run" in cmd and "--rm" in cmd
    assert any("/workspace" in str(c) for c in cmd)
    assert "container_strat.strategy" in cmd


def test_pq_run_container_mode_with_debug_uses_debugpy(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _write_project(tmp_path, "dbg-container")
    monkeypatch.setattr(
        "quantplatform.cli.run._find_compose_dir",
        lambda project_dir: tmp_path,
    )

    with patch("quantplatform.cli.run.httpx.post") as post, \
         patch("quantplatform.cli.run.subprocess.run") as sub_run, \
         patch("quantplatform.cli.run._git_sha", return_value="abc123"), \
         patch("quantplatform.cli.run._uv_lock_hash", return_value="deadbeef"):
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"strategy_id": "00000000-0000-0000-0000-000000000001", "created": False}
        post.return_value.raise_for_status.return_value = None
        sub_run.return_value.returncode = 0

        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["run", "dbg-container", "--container", "--debug"])
        finally:
            os.chdir(old)

    assert result.exit_code == 0
    cmd = sub_run.call_args.args[0]
    assert "debugpy" in cmd
    assert "0.0.0.0:5678" in cmd


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
