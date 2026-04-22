"""Dagster code location for the platform.

Empty Definitions for now; bronze/silver/gold assets land in Task 2.5.1,
strategy assets in Task 2.2, walk-forward in Task 3.4. The workspace.yaml
points at this module via `python_module: app.dagster_defs`.
"""

from __future__ import annotations

from dagster import Definitions

defs = Definitions()
