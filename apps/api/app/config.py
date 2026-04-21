"""Application configuration loaded from environment variables.

One settings object serves every role. Role-specific behaviour is expressed
through the `role` field; infrastructure endpoints and credentials are shared.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Role(StrEnum):
    api = "api"
    bff = "bff"
    idp = "idp"
    worker_proj_ui = "worker-proj-ui"
    worker_training = "worker-training"
    worker_inference_batch = "worker-inference-batch"
    worker_pipeline_bronze = "worker-pipeline-bronze"
    worker_pipeline_silver = "worker-pipeline-silver"
    scheduler = "scheduler"
    bridge_pgmq_http = "bridge-pgmq-http"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    role: Role = Field(default=Role.api, alias="ROLE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(alias="DATABASE_URL")

    storage_backend: str = Field(default="minio", alias="STORAGE_BACKEND")
    storage_endpoint: str = Field(default="http://localhost:9000", alias="STORAGE_ENDPOINT")
    storage_bucket: str = Field(default="quant-bronze", alias="STORAGE_BUCKET")
    storage_access_key: str = Field(default="minioadmin", alias="STORAGE_ACCESS_KEY")
    storage_secret_key: str = Field(default="minioadmin", alias="STORAGE_SECRET_KEY")

    mlflow_tracking_uri: str = Field(default="http://localhost:5000", alias="MLFLOW_TRACKING_URI")

    # Upstream OIDC provider — mock in dev, Google Workspace or Microsoft Entra in prod.
    # The `idp` role federates this; everything else verifies tokens minted by our `idp`.
    oidc_upstream_discovery_url: str = Field(
        default="http://mock-oidc:9800/.well-known/openid-configuration",
        alias="OIDC_UPSTREAM_DISCOVERY_URL",
    )
    oidc_upstream_client_id: str = Field(default="quant-platform", alias="OIDC_UPSTREAM_CLIENT_ID")
    oidc_upstream_client_secret: str = Field(
        default="mock-secret", alias="OIDC_UPSTREAM_CLIENT_SECRET"
    )
    oidc_upstream_name: str = Field(default="mock", alias="OIDC_UPSTREAM_NAME")

    # Browser-facing base URL for the upstream. When the upstream is reachable
    # from inside the docker network under a different hostname (e.g.
    # `mock-oidc:9800`) than the browser sees (`localhost:9800`), set this so
    # the IdP rewrites the authorization redirect to the browser-facing host.
    # Leave unset in prod — Google/Entra issuers are the same URL everywhere.
    oidc_upstream_browser_base: str | None = Field(default=None, alias="OIDC_UPSTREAM_BROWSER_BASE")

    # Our own IdP — where the `bff` sends users and where internal services fetch JWKS.
    idp_issuer: str = Field(default="http://idp:8001", alias="IDP_ISSUER")
    idp_internal_url: str = Field(default="http://idp:8001", alias="IDP_INTERNAL_URL")
    idp_client_id: str = Field(default="quant-bff", alias="IDP_CLIENT_ID")
    idp_client_secret: str = Field(default="dev-bff-secret", alias="IDP_CLIENT_SECRET")
    idp_signing_key_b64: str | None = Field(default=None, alias="IDP_SIGNING_KEY_B64")
    idp_signing_key_id: str = Field(default="qp-dev-1", alias="IDP_SIGNING_KEY_ID")
    idp_access_token_ttl_seconds: int = Field(default=900, alias="IDP_ACCESS_TOKEN_TTL_SECONDS")
    idp_refresh_token_ttl_seconds: int = Field(
        default=60 * 60 * 24 * 14, alias="IDP_REFRESH_TOKEN_TTL_SECONDS"
    )
    idp_token_audience: str = Field(default="quant-platform", alias="IDP_TOKEN_AUDIENCE")

    # BFF — where browser traffic arrives.
    bff_public_url: str = Field(default="http://localhost:8080", alias="BFF_PUBLIC_URL")
    bff_upstream_api_url: str = Field(default="http://api:8000", alias="BFF_UPSTREAM_API_URL")
    bff_session_idle_seconds: int = Field(default=60 * 30, alias="BFF_SESSION_IDLE_SECONDS")
    bff_session_absolute_seconds: int = Field(
        default=60 * 60 * 8, alias="BFF_SESSION_ABSOLUTE_SECONDS"
    )
    bff_session_cookie_secure: bool = Field(default=True, alias="BFF_SESSION_COOKIE_SECURE")
    # Required for the `bff` role; other roles don't touch session tokens, so default "".
    # The app fails loudly at first `seal()` call if it's empty when actually needed.
    bff_token_encryption_key_b64: str = Field(default="", alias="BFF_TOKEN_ENCRYPTION_KEY_B64")

    # Back-compat: legacy var read in some paths.
    session_jwt_signing_key: str = Field(default="", alias="SESSION_JWT_SIGNING_KEY")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
