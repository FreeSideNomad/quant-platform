"""Application settings loaded from environment variables."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_role: str = Field(default="api", alias="SERVICE_ROLE")
    database_url: str = Field(
        default="postgresql+asyncpg://qp:qp@localhost:15432/qp", alias="DATABASE_URL"
    )
    mlflow_tracking_uri: str = Field(
        default="http://localhost:15000", alias="MLFLOW_TRACKING_URI"
    )


def get_settings() -> Settings:
    return Settings()
