"""SDK-side runtime configuration, sourced from environment variables.

These are set by `pq up` (via .env / docker-compose) or directly by the
operator for host-mode strategies. No defaults that would work in
production — the SDK is explicit about its dependencies.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SDKSettings:
    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str


def get_settings() -> SDKSettings:
    return SDKSettings(
        s3_endpoint_url=os.environ.get("S3_ENDPOINT_URL", "http://localhost:19000"),
        s3_access_key=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
        s3_secret_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    )
