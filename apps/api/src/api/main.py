"""FastAPI application entry point."""
from __future__ import annotations

import json

import psycopg2
import psycopg2.extras
from fastapi import FastAPI
from pydantic import BaseModel, Field

from api import __version__
from api.settings import get_settings

settings = get_settings()

app = FastAPI(
    title="Quant Platform API",
    version=__version__,
)


def _connect():
    url = settings.database_url.replace("+asyncpg", "").replace("+psycopg2", "")
    return psycopg2.connect(url)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness + readiness probe."""
    return {
        "status": "ok",
        "role": settings.service_role,
        "version": __version__,
    }


class StrategyUpsert(BaseModel):
    name: str = Field(..., min_length=1)
    entry_point: str
    thresholds: dict = Field(default_factory=dict)
    git_sha: str | None = None
    uv_lock_hash: str | None = None


class StrategyUpsertResponse(BaseModel):
    strategy_id: str
    created: bool


@app.post("/strategies", response_model=StrategyUpsertResponse)
def upsert_strategy(body: StrategyUpsert) -> StrategyUpsertResponse:
    """Upsert a strategy by name. Returns strategy_id + whether a new row was created."""
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO strategies (name, entry_point, thresholds, git_sha, uv_lock_hash)
                VALUES (%s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (name) DO UPDATE
                  SET entry_point = EXCLUDED.entry_point,
                      thresholds = EXCLUDED.thresholds,
                      git_sha = EXCLUDED.git_sha,
                      uv_lock_hash = EXCLUDED.uv_lock_hash,
                      updated_at = NOW()
                RETURNING id, (xmax = 0) AS created
                """,
                (body.name, body.entry_point, json.dumps(body.thresholds),
                 body.git_sha, body.uv_lock_hash),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()
    return StrategyUpsertResponse(strategy_id=str(row["id"]), created=bool(row["created"]))
