"""worker-training role — drains the `training` PGMQ queue and executes jobs.

For the `local-cpu` profile, training runs in-process (fine for the demo
workload). For `local-gpu` / `cloud-gpu`, this role would dispatch to Cloud
Run Jobs or Vertex AI — left as TODOs with explicit error so we fail loudly
rather than silently fall back.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import text

from app.infra.db import session_scope
from app.infra.logging import configure_logging, get_logger
from app.infra.pgmq import PGMQMessage
from app.quant.pipeline import build_gold_features, load_bronze_to_silver
from app.quant.synthetic import DEFAULT_UNIVERSE, SyntheticConfig, generate
from app.quant.training import (
    export_summary,
    load_training_data,
    register_model_version,
    train_lgbm,
)
from app.workers.base import Worker

log = get_logger(__name__)


class TrainingWorker(Worker):
    queue_name = "training"
    concurrency = 1  # training is CPU-heavy; keep serial in-process
    visibility_timeout_seconds = 600

    async def handle(self, message: PGMQMessage) -> None:
        run_id = message.message.get("training_run_id")
        if not run_id:
            log.warning("training.missing_run_id", payload=message.message)
            return
        log.info("training.starting", run_id=run_id)

        # Pull the run spec
        async with session_scope() as session:
            r = await session.execute(
                text(
                    """
                    SELECT tr.id, tr.model_id, m.name, tr.compute_profile,
                           tr.as_of, tr.train_start, tr.train_end, tr.instruments,
                           tr.hyperparameters
                    FROM training_runs tr JOIN models m ON m.id = tr.model_id
                    WHERE tr.id = :id
                    """
                ),
                {"id": run_id},
            )
            row = r.first()
            if row is None:
                log.warning("training.run_not_found", run_id=run_id)
                return
            (
                _id,
                model_id,
                model_name,
                compute_profile,
                as_of,
                train_start,
                train_end,
                instruments,
                hyperparameters,
            ) = row
            await session.execute(
                text("UPDATE training_runs SET status='running' WHERE id=:id"),
                {"id": run_id},
            )

        if compute_profile not in ("local-cpu",):
            await self._fail(run_id, f"compute_profile {compute_profile!r} not wired in this build")
            return

        try:
            # Ensure we have silver and gold materialised. For the demo, we
            # synthesise if silver is empty.
            async with session_scope() as session:
                r = await session.execute(text("SELECT count(*) FROM daily_prices_silver"))
                silver_count = (r.first() or (0,))[0]
                if silver_count == 0:
                    log.info("training.seeding_synthetic_silver")
                    df = generate(
                        SyntheticConfig(
                            instruments=DEFAULT_UNIVERSE,
                            start=train_start,
                            end=as_of,
                        )
                    )
                    await load_bronze_to_silver(
                        session, df, source_uri="synthetic", backdate_knowable_at=True
                    )

            async with session_scope() as session:
                await build_gold_features(session, as_of=as_of)

            async with session_scope() as session:
                df_train = await load_training_data(
                    session,
                    as_of=as_of,
                    train_start=train_start,
                    train_end=train_end,
                    instruments=list(instruments) or None,
                )

            artefact = train_lgbm(df_train, params=dict(hyperparameters or {}))

            mlflow_version = register_model_version(
                model_name=model_name,
                model_path=artefact.model_path,
                mlflow_run_id=artefact.mlflow_run_id,
            )

            async with session_scope() as session:
                import uuid

                version_id = str(uuid.uuid4())
                await session.execute(
                    text(
                        """
                        INSERT INTO model_versions(
                          id, model_id, training_run_id, version, stage,
                          mlflow_model_version, metrics
                        ) VALUES (:id, :mid, :trid, :v, 'draft', :mv, CAST(:m AS jsonb))
                        """
                    ),
                    {
                        "id": version_id,
                        "mid": model_id,
                        "trid": run_id,
                        "v": mlflow_version or artefact.mlflow_run_id[:8],
                        "mv": mlflow_version,
                        "m": json.dumps(artefact.metrics),
                    },
                )
                await session.execute(
                    text(
                        """
                        UPDATE training_runs SET
                          status='completed',
                          completed_at=:now,
                          mlflow_run_id=:rid,
                          metrics=CAST(:m AS jsonb),
                          model_version=:v,
                          artefact_uri=:a
                        WHERE id=:id
                        """
                    ),
                    {
                        "id": run_id,
                        "now": datetime.now(UTC),
                        "rid": artefact.mlflow_run_id,
                        "m": json.dumps(export_summary(artefact)),
                        "v": mlflow_version,
                        "a": artefact.model_path,
                    },
                )
            log.info(
                "training.completed",
                run_id=run_id,
                metrics=artefact.metrics,
                version=mlflow_version,
            )
        except Exception as exc:
            log.error("training.failed", run_id=run_id, error=str(exc))
            await self._fail(run_id, str(exc))
            raise

    async def _fail(self, run_id: str, reason: str) -> None:
        async with session_scope() as session:
            await session.execute(
                text(
                    """
                    UPDATE training_runs SET
                      status='failed', completed_at=:now, error=:e
                    WHERE id=:id
                    """
                ),
                {"id": run_id, "now": datetime.now(UTC), "e": reason},
            )


async def main() -> None:
    configure_logging()
    await TrainingWorker().run()


if __name__ == "__main__":
    asyncio.run(main())
