"""Run lifecycle: taking the brand+competitors snapshot, idempotency-key
handling, the "already active" 409 check, and enqueueing the pipeline job
(CLAUDE.md section 3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Brand, Run, RunStatus
from app.worker.main import QUEUE_NAME

ACTIVE_STATUSES = (RunStatus.QUEUED, RunStatus.RUNNING)


class RunAlreadyActiveError(Exception):
    def __init__(self, run_id: uuid.UUID) -> None:
        super().__init__(f"A run is already queued/running for this brand: {run_id}")
        self.run_id = run_id


def brand_snapshot(brand: Brand) -> dict:
    return {
        "name": brand.name,
        "domain": brand.domain,
        "description": brand.description,
        "industry": brand.industry,
        "location_code": brand.location_code,
        "language_code": brand.language_code,
        "competitors": [{"name": c.name, "domain": c.domain} for c in brand.competitors],
    }


def create_run(
    session: Session,
    redis_client: Redis,
    settings: Settings,
    brand: Brand,
    *,
    trigger: str = "manual",
    idempotency_key: str | None = None,
) -> tuple[Run, bool]:
    """Returns (run, created). A repeated request with the same
    `idempotency_key` for this brand returns the existing run unchanged
    (created=False) instead of creating a duplicate or raising 409."""
    # Serialize the active-run check per brand across API threads/processes.
    session.execute(select(Brand).where(Brand.id == brand.id).with_for_update()).scalar_one()
    if idempotency_key:
        existing = session.execute(
            select(Run).where(Run.brand_id == brand.id, Run.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

    active = session.execute(
        select(Run).where(Run.brand_id == brand.id, Run.status.in_(ACTIVE_STATUSES))
    ).scalar_one_or_none()
    if active is not None:
        raise RunAlreadyActiveError(active.id)

    run = Run(
        brand_id=brand.id,
        status=RunStatus.QUEUED,
        trigger=trigger,
        idempotency_key=idempotency_key,
        brand_snapshot=brand_snapshot(brand),
    )
    session.add(run)
    session.flush()
    run.trace_id = str(run.id)
    session.commit()

    # Imported as a dotted string (not a direct callable) so enqueueing a
    # run never has to import the pipeline/LangGraph stack into the API
    # process — only the worker process does.
    from rq import Queue
    from rq.job import Callback

    queue = Queue(QUEUE_NAME, connection=redis_client)
    try:
        queue.enqueue(
            "app.pipeline.runner.execute_run",
            str(run.id),
            job_id=f"run-{run.id}",
            job_timeout=settings.run_timeout_seconds,
            result_ttl=0,
            on_failure=Callback("app.worker.callbacks.job_failed"),
        )
    except Exception:
        run.status = RunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.error_summary = "Could not enqueue the analysis. Check Redis availability and start a new run."
        session.commit()
        raise
    return run, True
