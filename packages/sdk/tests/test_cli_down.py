"""Unit tests for `qp down` — mocks docker compose subprocess."""
from __future__ import annotations

from unittest.mock import patch

from quantplatform.cli.main import app


def test_qp_down_invokes_docker_compose(runner) -> None:
    with patch("quantplatform.cli.down.subprocess.run") as run:
        run.return_value.returncode = 0
        result = runner.invoke(app, ["down"])
    assert result.exit_code == 0
    run.assert_called_once()
    args = run.call_args.args[0]
    assert args[:2] == ["docker", "compose"]
    assert "down" in args


def test_qp_down_does_not_remove_volumes_by_default(runner) -> None:
    with patch("quantplatform.cli.down.subprocess.run") as run:
        run.return_value.returncode = 0
        runner.invoke(app, ["down"])
    args = run.call_args.args[0]
    assert "-v" not in args
    assert "--volumes" not in args
