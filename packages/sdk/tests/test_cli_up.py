"""Unit tests for `pq up` — mocks docker compose subprocess."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from quantplatform.cli.main import app


_FAKE_PLATFORM = Path("/fake/platform")


def test_pq_up_invokes_docker_compose_with_build(runner) -> None:
    with (
        patch("quantplatform.cli.up.require_platform_dir", return_value=_FAKE_PLATFORM),
        patch("quantplatform.cli.up._clean_stale_pq_containers"),
        patch("quantplatform.cli.up.subprocess.run") as run,
    ):
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
    # subprocess runs in the configured platform dir, not cwd
    assert run.call_args.kwargs["cwd"] == _FAKE_PLATFORM


def test_pq_up_no_build_flag_skips_rebuild(runner) -> None:
    with (
        patch("quantplatform.cli.up.require_platform_dir", return_value=_FAKE_PLATFORM),
        patch("quantplatform.cli.up._clean_stale_pq_containers"),
        patch("quantplatform.cli.up.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        result = runner.invoke(app, ["up", "--no-build"])
    assert result.exit_code == 0
    args = run.call_args.args[0]
    assert "--build" not in args


def test_pq_up_propagates_nonzero_exit(runner) -> None:
    with (
        patch("quantplatform.cli.up.require_platform_dir", return_value=_FAKE_PLATFORM),
        patch("quantplatform.cli.up._clean_stale_pq_containers"),
        patch("quantplatform.cli.up.subprocess.run") as run,
    ):
        run.return_value.returncode = 2
        result = runner.invoke(app, ["up"])
    assert result.exit_code == 2


def test_pq_up_errors_when_platform_dir_not_configured(runner) -> None:
    with patch(
        "quantplatform.cli.up.require_platform_dir",
        side_effect=RuntimeError("platform directory not configured. Run `pq init`."),
    ):
        result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert "pq init" in result.output


def test_pq_up_cleans_stale_pq_containers_before_starting(runner) -> None:
    """Stopped pq-* orphan containers should be removed before compose up."""
    with (
        patch("quantplatform.cli.up.require_platform_dir", return_value=_FAKE_PLATFORM),
        patch("quantplatform.cli.up.subprocess.run") as run,
    ):
        # subprocess.run calls:
        # 1. docker ps -a --filter name=pq- ...
        # 2. docker rm -f pq-foo pq-bar ...  (only if something to remove)
        # 3. docker compose up -d --build
        def side_effect(cmd, **kw):
            from types import SimpleNamespace
            if cmd[:2] == ["docker", "ps"]:
                return SimpleNamespace(
                    returncode=0,
                    stdout="pq-postgres\texited\npq-mock-oidc\texited\n",
                )
            return SimpleNamespace(returncode=0)
        run.side_effect = side_effect
        result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    calls = [c.args[0] for c in run.call_args_list]
    assert calls[0][:2] == ["docker", "ps"]
    rm_calls = [c for c in calls if c[:3] == ["docker", "rm", "-f"]]
    assert rm_calls, f"expected a `docker rm -f` call after stale ps probe; got {calls}"
    assert "pq-postgres" in rm_calls[0]
    assert "pq-mock-oidc" in rm_calls[0]
    assert calls[-1][:2] == ["docker", "compose"]
