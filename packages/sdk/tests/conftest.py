"""Shared test fixtures for the quantplatform package."""
import pytest
from typer.testing import CliRunner

@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
