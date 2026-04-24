"""Unit tests for `qp doctor` — mocks all probes."""
from __future__ import annotations

from unittest.mock import patch

from quantplatform.cli.main import app


def test_qp_doctor_all_checks_pass(runner) -> None:
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


def test_qp_doctor_fails_on_missing_docker(runner) -> None:
    with (
        patch("quantplatform.cli.doctor._check_docker", return_value=(False, "Docker not installed")),
        patch("quantplatform.cli.doctor._check_compose", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_python", return_value=(True, "")),
        patch("quantplatform.cli.doctor._check_ports", return_value=(True, "")),
    ):
        result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert "Docker not installed" in result.stdout


def test_qp_doctor_fails_on_port_conflict(runner) -> None:
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
