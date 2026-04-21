"""Base Worker — every worker role subclasses this and supplies `handle`.

The loop is responsible for:
- pulling a batch from PGMQ
- processing each message with bounded concurrency
- idempotency (deferred to subclasses via the `processed_events` table)
- acking on success, letting visibility timeout trigger retry on failure
- graceful shutdown on SIGTERM
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from abc import ABC, abstractmethod

from app.infra.db import session_scope
from app.infra.logging import get_logger
from app.infra.pgmq import PGMQMessage
from app.infra.pgmq import delete as pgmq_delete
from app.infra.pgmq import read as pgmq_read

log = get_logger(__name__)


class Worker(ABC):
    queue_name: str
    concurrency: int = 4
    visibility_timeout_seconds: int = 60
    batch_size: int = 10
    poll_idle_sleep_seconds: float = 0.5

    def __init__(self) -> None:
        self._shutdown = asyncio.Event()
        self._sem = asyncio.Semaphore(self.concurrency)

    @abstractmethod
    async def handle(self, message: PGMQMessage) -> None:
        """Process one message. Raise to trigger retry via visibility timeout."""

    async def run(self) -> None:
        self._install_signal_handlers()
        log.info("worker.start", queue=self.queue_name, concurrency=self.concurrency)
        while not self._shutdown.is_set():
            try:
                await self._pull_and_process_batch()
            except Exception as exc:
                log.error("worker.batch_error", error=str(exc))
                await asyncio.sleep(1.0)
        log.info("worker.stopped", queue=self.queue_name)

    async def _pull_and_process_batch(self) -> None:
        async with session_scope() as session:
            messages = await pgmq_read(
                session,
                self.queue_name,
                self.visibility_timeout_seconds,
                self.batch_size,
            )
        if not messages:
            await asyncio.sleep(self.poll_idle_sleep_seconds)
            return
        tasks = [self._process_one(m) for m in messages]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_one(self, message: PGMQMessage) -> None:
        async with self._sem:
            try:
                await self.handle(message)
            except Exception as exc:
                log.warning(
                    "worker.handler_error",
                    queue=self.queue_name,
                    msg_id=message.msg_id,
                    error=str(exc),
                )
                return
            async with session_scope() as session:
                await pgmq_delete(session, self.queue_name, message.msg_id)

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            # Windows does not support add_signal_handler; tolerate silently.
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._shutdown.set)
