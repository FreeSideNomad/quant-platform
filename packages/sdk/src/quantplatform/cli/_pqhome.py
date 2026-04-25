"""User-home state for `pq` — `~/.pq/` is the single root directory.

Layout (subdirs are created lazily as features need them):

    ~/.pq/
    ├── config.toml       # persistent settings (M3: platform_dir)
    ├── credentials       # OAuth tokens — pq auth login (M7, per spec §6.1.2)
    ├── logs/             # per-command logs (M4+)
    ├── state/            # session / run state (M4+)
    └── cache/            # work-in-progress, scratch (M4+)

Override the root via `PQ_HOME` env var (useful for tests + multi-tenant
shells). config.toml schema:

    [platform]
    dir = "/abs/path/to/quant-platform"     # repo root (where docker-compose.yml lives)
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


def _home() -> Path:
    return Path(os.environ.get("PQ_HOME", str(Path.home() / ".pq"))).expanduser()


PQ_HOME = _home()
CONFIG_PATH = PQ_HOME / "config.toml"
LOGS_DIR = PQ_HOME / "logs"
STATE_DIR = PQ_HOME / "state"
CACHE_DIR = PQ_HOME / "cache"


def ensure_home() -> Path:
    """Create ~/.pq/ + standard subdirs if absent. Returns the home path."""
    home = _home()
    for d in (home, home / "logs", home / "state", home / "cache"):
        d.mkdir(parents=True, exist_ok=True)
    return home


def load_config() -> dict[str, Any]:
    """Read ~/.pq/config.toml; return empty dict if missing."""
    cfg_path = _home() / "config.toml"
    if not cfg_path.is_file():
        return {}
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)


def save_config(data: dict[str, Any]) -> None:
    """Write data as TOML to ~/.pq/config.toml.

    Uses a hand-rolled writer (Python stdlib has no tomllib.dumps) so we
    don't pull in tomli-w just for this. Only supports the small surface
    we actually use (string values under named tables); errors on anything
    fancier so we notice if someone needs a richer config format later.
    """
    ensure_home()
    cfg_path = _home() / "config.toml"
    lines: list[str] = []
    for table_name, table in data.items():
        if not isinstance(table, dict):
            raise ValueError(f"top-level config keys must be tables; got {table_name!r}")
        lines.append(f"[{table_name}]")
        for key, value in table.items():
            if not isinstance(value, str):
                raise ValueError(
                    f"only string values supported (M3 simplification); "
                    f"got {table_name}.{key} = {value!r}"
                )
            # Escape backslashes + double-quotes for TOML basic strings
            esc = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{esc}"')
        lines.append("")
    cfg_path.write_text("\n".join(lines))


def get_platform_dir() -> Path | None:
    """Resolve the platform repo root.

    Priority: env QP_PLATFORM_DIR > ~/.pq/config.toml [platform] dir.
    Returns None if neither is set. Does NOT validate the path exists —
    callers should and surface a useful error.
    """
    env = os.environ.get("QP_PLATFORM_DIR")
    if env:
        return Path(env).expanduser()
    cfg = load_config()
    platform_dir = cfg.get("platform", {}).get("dir")
    if platform_dir:
        return Path(platform_dir).expanduser()
    return None


def require_platform_dir() -> Path:
    """Like get_platform_dir but raises with a helpful message if missing."""
    p = get_platform_dir()
    if p is None:
        raise RuntimeError(
            "platform directory not configured. Run `pq init` from the "
            "quant-platform repo root, or set QP_PLATFORM_DIR=/abs/path."
        )
    if not (p / "docker-compose.yml").is_file():
        raise RuntimeError(
            f"configured platform directory {p} has no docker-compose.yml. "
            f"Run `pq init` again with the correct path, or unset stale config."
        )
    return p
