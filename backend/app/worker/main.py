"""RQ worker entrypoint: `python -m app.worker.main`.

Runs in its own container (same image as the API). Listens on the `runs`
queue — from Phase 3 onward, `POST /brands/{id}/runs` enqueues the pipeline
job here so a long analysis run never blocks the HTTP request and survives
an API restart.
"""

from __future__ import annotations

import redis
from rq import Queue, Worker

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import init_engine

QUEUE_NAME = "runs"

logger = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    init_engine(settings.database_url)

    connection = redis.Redis.from_url(settings.redis_url)
    queue = Queue(QUEUE_NAME, connection=connection)
    worker = Worker([queue], connection=connection)

    logger.info("worker_starting", queue=QUEUE_NAME)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
