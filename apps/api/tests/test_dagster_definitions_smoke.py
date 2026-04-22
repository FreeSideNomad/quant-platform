"""Smoke: the empty Definitions module imports cleanly."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_dagster_defs_module_imports():
    from app.dagster_defs import defs
    from dagster import Definitions

    assert isinstance(defs, Definitions)
