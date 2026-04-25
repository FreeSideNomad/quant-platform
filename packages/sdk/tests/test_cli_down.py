"""Unit tests for `pq down` — mocks docker compose subprocess."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from quantplatform.cli.main import app


_FAKE_PLATFORM = Path("/fake/platform")


def test_pq_down_invokes_docker_compose(runner) -> None:
    with (
        patch("quantplatform.cli.down.require_platform_dir", return_value=_FAKE_PLATFORM),
        patch("quantplatform.cli.down.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        result = runner.invoke(app, ["down"])
    assert result.exit_code == 0
    run.assert_called_once()
    args = run.call_args.args[0]
    assert args[:2] == ["docker", "compose"]
    assert "down" in args
    assert run.call_args.kwargs["cwd"] == _FAKE_PLATFORM


def test_pq_down_does_not_remove_volumes_by_default(runner) -> None:
    with (
        patch("quantplatform.cli.down.require_platform_dir", return_value=_FAKE_PLATFORM),
        patch("quantplatform.cli.down.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        runner.invoke(app, ["down"])
    args = run.call_args.args[0]
    assert "-v" not in args
    assert "--volumes" not in args


def test_pq_down_with_volumes_flag_removes_volumes(runner) -> None:
    """`pq down -v` (and `--volumes`) passes -v through to docker compose down."""
    for flag in ("-v", "--volumes"):
        with (
            patch("quantplatform.cli.down.require_platform_dir", return_value=_FAKE_PLATFORM),
            patch("quantplatform.cli.down.subprocess.run") as run,
        ):
            run.return_value.returncode = 0
            result = runner.invoke(app, ["down", flag])
        assert result.exit_code == 0, f"flag={flag!r} output={result.output!r}"
        args = run.call_args.args[0]
        assert "-v" in args, f"flag={flag!r} args={args!r}"
        assert "Volumes wiped" in result.output


def test_pq_down_errors_when_platform_dir_not_configured(runner) -> None:
    with patch(
        "quantplatform.cli.down.require_platform_dir",
        side_effect=RuntimeError("platform directory not configured. Run `pq init`."),
    ):
        result = runner.invoke(app, ["down"])
    assert result.exit_code == 1
    assert "pq init" in result.output
