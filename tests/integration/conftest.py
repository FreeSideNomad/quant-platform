"""Integration-test fixtures: bring up the compose stack once per session."""
from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def compose_up() -> Iterator[None]:
    """Ensure the docker-compose stack is up for the duration of the test session."""
    subprocess.run(
        ["docker", "compose", "up", "-d", "--wait"],
        cwd=REPO_ROOT,
        check=True,
    )
    yield
    subprocess.run(
        ["docker", "compose", "down"],
        cwd=REPO_ROOT,
        check=True,
    )
