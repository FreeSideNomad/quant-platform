"""`qp doctor` — verify local prerequisites."""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys

import typer
from rich.console import Console

console = Console()

REQUIRED_PORTS: tuple[int, ...] = (15432, 19000, 19001, 15000, 14444, 18000, 15173)


def _check_docker() -> tuple[bool, str]:
    if shutil.which("docker") is None:
        return False, "Docker not installed"
    result = subprocess.run(
        ["docker", "--version"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return False, "Docker not responding"
    return True, result.stdout.strip()


def _check_compose() -> tuple[bool, str]:
    result = subprocess.run(
        ["docker", "compose", "version"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return False, "docker compose subcommand not available"
    return True, result.stdout.strip().splitlines()[0]


def _check_python() -> tuple[bool, str]:
    major, minor = sys.version_info[:2]
    version_str = f"Python {major}.{minor}.{sys.version_info.micro}"
    if (major, minor) < (3, 12):
        return False, f"{version_str} — need >=3.12"
    return True, version_str


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _stack_is_running() -> bool:
    """Return True if the local docker-compose stack has any running containers."""
    result = subprocess.run(
        ["docker", "compose", "ps", "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _check_ports() -> tuple[bool, str]:
    busy = [p for p in REQUIRED_PORTS if not _port_is_free(p)]
    if not busy:
        return True, "All required ports free"
    if _stack_is_running():
        return True, f"{len(busy)} port(s) held by running qp stack (expected)"
    return False, f"Port {busy[0]} already in use"


def doctor() -> None:
    """Verify Docker, compose, Python version, and port availability."""
    checks: list[tuple[str, tuple[bool, str]]] = [
        ("Docker", _check_docker()),
        ("Compose", _check_compose()),
        ("Python", _check_python()),
        ("Ports", _check_ports()),
    ]
    all_ok = all(ok for _, (ok, _) in checks)
    for name, (ok, detail) in checks:
        icon = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        console.print(f"{icon} {name}: {detail}")
    if not all_ok:
        raise typer.Exit(code=1)
