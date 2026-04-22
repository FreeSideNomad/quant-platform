"""Auto-loaded Dagster code location for per-strategy assets.

Every .py file in this directory is a self-contained module with one
or more `@asset`-decorated functions. The package's __init__ scans
the directory at import time and re-exports the assets so
app.dagster_defs.Definitions can include them.
"""

from __future__ import annotations

import importlib
import pkgutil

from dagster import AssetsDefinition

_loaded: list[AssetsDefinition] = []

for module_info in pkgutil.iter_modules(__path__):
    module = importlib.import_module(f"{__name__}.{module_info.name}")
    for value in vars(module).values():
        if isinstance(value, AssetsDefinition):
            _loaded.append(value)


def all_strategy_assets() -> list[AssetsDefinition]:
    return list(_loaded)
