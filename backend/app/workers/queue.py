"""Cola de trabajos en proceso (asyncio). En producción puede sustituirse por Redis/RQ/Celery."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from app.db.session import async_session_factory
from app.services.pipeline import run_job

logger = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, workers: int = 1) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers = workers
        self._tasks: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        for i in range(self._workers):
            self._tasks.append(asyncio.create_task(self._worker_loop(i)))
        logger.info("Cola iniciada con %s worker(s)", self._workers)

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        self._started = False

    async def enqueue(self, job_id: str) -> None:
        await self._queue.put(job_id)
        logger.info("Job encolado: %s (cola=%s)", job_id, self._queue.qsize())

    async def _worker_loop(self, worker_id: int) -> None:
        while True:
            job_id = await self._queue.get()
            try:
                logger.info("[worker-%s] procesando %s", worker_id, job_id)
                async with async_session_factory() as session:
                    await run_job(session, job_id)
            except Exception:  # noqa: BLE001
                logger.exception("[worker-%s] error en %s", worker_id, job_id)
            finally:
                self._queue.task_done()


_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        _queue = JobQueue(workers=1)
    return _queue
