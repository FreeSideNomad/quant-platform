"""Unit tests for `pq doctor` — mocks all probes."""
from __future__ import annotations

from unittest.mock import patch

from quantplatform.cli.doctor import _check_ports
from quantplatform.cli.main import app


def test_pq_doctor_all_checks_pass(runner) -> None:
    with (
        patch("quantplatform.cli.doctor._check_docker", return_value=(True, "Docker 27.3.1")),
        patch("quantplatform.cli.doctor._check_compose", return_value=(True, "Compose v2.29")),
        patch("quantplatform.cli.doctor._check_python", return_value=(True, "Python 3.12.5")),
        patch("quantplatform.cli.doctor._check_ports", return_value=(True, "All required ports free")),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "Docker 27.3.1" in result.stdout
    assert "All required ports free" in result.stdout


def test_pq_doctor_fails_on_missing_docker(runner) -> None:
    with (
        patch("quantplatform.cli.doctor._check_docker", return_value=(False, "Docker not installed")),
        patch("quantplatform.cli.doctor._check_compose", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_python", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_ports", return_value=(True, "")),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Docker not installed" in result.stdout


def test_pq_doctor_fails_on_port_conflict(runner) -> None:
    with (
        patch("quantplatform.cli.doctor._check_docker", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_compose", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_python", return_value=(True, "")),
        patch(
            "quantplatform.cli.doctor._check_ports",
            return_value=(False, "Port 18000 already in use"),
        ),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Port 18000 already in use" in result.stdout


def test_check_ports_passes_when_stack_up_holds_busy_ports() -> None:
    with (
        patch("quantplatform.cli.doctor._port_is_free", return_value=False),
        patch("quantplatform.cli.doctor._stack_is_running", return_value=True),
    ):
        ok, detail = _check_ports()
    assert ok is True
    assert "held by running pq stack" in detail


def test_check_ports_fails_when_stack_down_and_port_busy() -> None:
    with (
        patch("quantplatform.cli.doctor._port_is_free", return_value=False),
        patch("quantplatform.cli.doctor._stack_is_running", return_value=False),
    ):
        ok, detail = _check_ports()
    assert ok is False
    assert "already in use" in detail


def test_check_ports_passes_when_all_free() -> None:
    with patch("quantplatform.cli.doctor._port_is_free", return_value=True):
        ok, detail = _check_ports()
    assert ok is True
    assert detail == "All required ports free"
