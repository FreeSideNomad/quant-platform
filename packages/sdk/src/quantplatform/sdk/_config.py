"""SDK-side runtime configuration, sourced from environment variables.

The user-facing surface is PQ_-prefixed (`PQ_S3_ENDPOINT_URL`,
`PQ_S3_ACCESS_KEY`, `PQ_S3_SECRET_KEY`, `PQ_MLFLOW_TRACKING_URI`,
`PQ_DATABASE_URL`) so it never collides with anything the user has in
their shell for unrelated work.

Some downstream third-party libs (boto3, MLflow's S3 artifact store)
read non-PQ env names directly — `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `MLFLOW_S3_ENDPOINT_URL`. The SDK shims those
in `apply_mlflow_s3_env()`, copying values from `PQ_S3_*` into the
process environment just-in-time. If the user already has different
`AWS_*` values set (e.g. real AWS credentials for their day job), the
shim warns once and overrides — silent override is dangerous.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SDKSettings:
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str


def get_settings() -> SDKSettings:
    return SDKSettings(
        s3_endpoint_url=os.environ.get("PQ_S3_ENDPOINT_URL", "http://localhost:19000"),
        s3_access_key=os.environ.get("PQ_S3_ACCESS_KEY", "minioadmin"),
        s3_secret_key=os.environ.get("PQ_S3_SECRET_KEY", "minioadmin"),
    )


# Map of PQ_* env-var name → AWS-world env-var name that boto3 / MLflow
# read. The shim in apply_mlflow_s3_env() copies values across this map.
_PQ_TO_AWS_ENV = {
    "PQ_S3_ACCESS_KEY": "AWS_ACCESS_KEY_ID",
    "PQ_S3_SECRET_KEY": "AWS_SECRET_ACCESS_KEY",
    "PQ_S3_ENDPOINT_URL": "MLFLOW_S3_ENDPOINT_URL",
}


def apply_mlflow_s3_env() -> None:
    """Translate PQ_S3_* into AWS_*/MLFLOW_S3_ENDPOINT_URL on os.environ.

    Idempotent. Called by `Strategy.train_and_validate` before any MLflow
    artifact upload. If the user already has a conflicting `AWS_*` /
    `MLFLOW_S3_ENDPOINT_URL` set in their shell (e.g. real AWS creds),
    log a warning and override — the strategy subprocess must talk to
    the local MinIO, not real AWS, but the user deserves to know we
    shadowed their value.
    """
    settings = get_settings()
    new_values = {
        "AWS_ACCESS_KEY_ID": settings.s3_access_key,
        "AWS_SECRET_ACCESS_KEY": settings.s3_secret_key,
        "MLFLOW_S3_ENDPOINT_URL": settings.s3_endpoint_url,
    }
    for aws_name, new_value in new_values.items():
        existing = os.environ.get(aws_name)
        if existing is not None and existing != new_value:
            log.warning(
                "shadowing pre-existing %s=%r with %r (sourced from PQ_S3_* / "
                "MinIO defaults). Set PQ_S3_* if you want a different value; "
                "the strategy subprocess won't reach real AWS.",
                aws_name,
                _redact(existing),
                _redact(new_value),
            )
        os.environ[aws_name] = new_value


def _redact(value: str) -> str:
    """Redact env-var values to head+tail so credentials don't leak to logs."""
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}…{value[-3:]}"
