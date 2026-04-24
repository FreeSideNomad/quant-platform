"""Unit tests for `pq up` — mocks docker compose subprocess."""
from __future__ import annotations

from unittest.mock import patch

from quantplatform.cli.main import app


def test_pq_up_invokes_docker_compose_with_build(runner) -> None:
    with patch("quantplatform.cli.up.subprocess.run") as run:
        run.return_value.returncode = 0
        result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    run.assert_called_once()
    args = run.call_args.args[0]
    assert args[:2] == ["docker", "compose"]
    assert "up" in args
    assert "-d" in args
    # --build is the default so source changes (api, ui, migrations) always land.
    assert "--build" in args


def test_pq_up_no_build_flag_skips_rebuild(runner) -> None:
    with patch("quantplatform.cli.up.subprocess.run") as run:
        run.return_value.returncode = 0
        result = runner.invoke(app, ["up", "--no-build"])
    assert result.exit_code == 0
    args = run.call_args.args[0]
    assert "--build" not in args


def test_pq_up_propagates_nonzero_exit(runner) -> None:
    with patch("quantplatform.cli.up.subprocess.run") as run:
        run.return_value.returncode = 2
        result = runner.invoke(app, ["up"])
    assert result.exit_code == 2
