"""Unit tests for `pq init` and the ~/.pq config helpers."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quantplatform.cli.main import app


def _normalized(s: str) -> str:
    """Collapse whitespace so wrap-induced newlines don't break substring asserts."""
    return " ".join(s.split())


def test_pq_init_writes_config(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fake platform dir
    platform = tmp_path / "platform"
    platform.mkdir()
    (platform / "docker-compose.yml").write_text(
        "services:\n  postgres:\n    container_name: pq-postgres\n"
    )

    # Redirect ~/.pq to a tmp location
    pq_home = tmp_path / "pqhome"
    monkeypatch.setenv("PQ_HOME", str(pq_home))

    result = runner.invoke(app, ["init", str(platform)])
    assert result.exit_code == 0, result.output
    assert "Recorded" in result.output

    cfg_file = pq_home / "config.toml"
    assert cfg_file.is_file()
    body = cfg_file.read_text()
    assert "[platform]" in body
    assert str(platform.resolve()) in body


def test_pq_init_rejects_dir_without_compose(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PQ_HOME", str(tmp_path / "pqhome"))
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["init", str(empty)])
    assert result.exit_code == 1
    assert "no docker-compose.yml" in _normalized(result.output)


def test_pq_init_rejects_unrelated_compose(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Compose file must contain the canonical pq-postgres container_name."""
    monkeypatch.setenv("PQ_HOME", str(tmp_path / "pqhome"))
    other = tmp_path / "other"
    other.mkdir()
    (other / "docker-compose.yml").write_text("services:\n  web:\n    image: nginx\n")
    result = runner.invoke(app, ["init", str(other)])
    assert result.exit_code == 2
    assert "doesn't look like" in _normalized(result.output)


def test_pq_init_default_uses_cwd(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    platform = tmp_path / "platform"
    platform.mkdir()
    (platform / "docker-compose.yml").write_text(
        "services:\n  postgres:\n    container_name: pq-postgres\n"
    )
    pq_home = tmp_path / "pqhome"
    monkeypatch.setenv("PQ_HOME", str(pq_home))

    old_cwd = os.getcwd()
    os.chdir(platform)
    try:
        result = runner.invoke(app, ["init"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    # Assert the config file was written with the resolved cwd, not the
    # rich-formatted output (which can wrap mid-path).
    cfg = (pq_home / "config.toml").read_text()
    assert str(platform.resolve()) in cfg


def test_get_platform_dir_env_overrides_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PQ_HOME", str(tmp_path / "pqhome"))
    monkeypatch.setenv("QP_PLATFORM_DIR", "/from/env")

    # Even with no config file, env should resolve
    from quantplatform.cli._pqhome import get_platform_dir
    assert get_platform_dir() == Path("/from/env")


def test_require_platform_dir_raises_with_helpful_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PQ_HOME", str(tmp_path / "pqhome"))
    monkeypatch.delenv("QP_PLATFORM_DIR", raising=False)

    from quantplatform.cli._pqhome import require_platform_dir
    with pytest.raises(RuntimeError, match="not configured.*pq init"):
        require_platform_dir()
