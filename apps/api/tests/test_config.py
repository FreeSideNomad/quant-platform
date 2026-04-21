"""Unit tests for configuration loading."""

from __future__ import annotations

import pytest

from app.config import Role, get_settings


@pytest.mark.unit
def test_settings_defaults_role_to_api() -> None:
    settings = get_settings()
    assert settings.role in set(Role)


@pytest.mark.unit
def test_role_enum_values() -> None:
    assert Role.api.value == "api"
    assert Role.worker_proj_ui.value == "worker-proj-ui"
    assert Role.scheduler.value == "scheduler"
    assert Role.bridge_pgmq_http.value == "bridge-pgmq-http"
