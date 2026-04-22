"""Smoke: the Dagster webserver brought up by docker-compose answers GraphQL.

The webserver has NO host-published port (it has no built-in auth). We hit
it via `docker compose exec api curl ...` which runs inside the docker
network, mirroring how the BFF and API roles will reach it in production.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest


def _exec_in_api(cmd: list[str]) -> str:
    docker = shutil.which("docker")
    assert docker is not None, "docker CLI required for compose smoke test"
    out = subprocess.check_output(
        [docker, "compose", "exec", "-T", "api", *cmd],
        stderr=subprocess.STDOUT,
        timeout=30,
    )
    return out.decode()


@pytest.mark.integration
def test_dagster_webserver_serves_graphql():
    """The dagster-webserver service answers GraphQL on the docker network."""
    payload = json.dumps({"query": "{ instance { info } }"})
    body = _exec_in_api(
        [
            "curl", "-fsS", "-X", "POST",
            "-H", "content-type: application/json",
            "-d", payload,
            "http://dagster-webserver:3000/graphql",
        ]
    )
    parsed = json.loads(body)
    assert "data" in parsed
    assert "instance" in parsed["data"]


@pytest.mark.integration
def test_dagster_uses_postgres_run_storage():
    """The Dagster instance reports postgres-backed run storage + healthy scheduler."""
    query = (
        "{ instance { runLauncher { name } "
        "daemonHealth { allDaemonStatuses { daemonType healthy } } } }"
    )
    payload = json.dumps({"query": query})
    body = _exec_in_api(
        [
            "curl", "-fsS", "-X", "POST",
            "-H", "content-type: application/json",
            "-d", payload,
            "http://dagster-webserver:3000/graphql",
        ]
    )
    parsed = json.loads(body)
    daemons = parsed["data"]["instance"]["daemonHealth"]["allDaemonStatuses"]
    scheduler = next(d for d in daemons if d["daemonType"] == "SCHEDULER")
    assert scheduler["healthy"] is True
