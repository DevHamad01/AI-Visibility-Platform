"""Record failures that occur outside the pipeline's own exception guard."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.config import get_settings
from app.db.base import get_engine, get_session, init_engine, remove_session
from app.db.models import Run, RunStageStatus, RunStatus


def _mark_failed(job, reason: str) -> None:
    try:
        get_engine()
    except RuntimeError:
        init_engine(get_settings().database_url)
    session = get_session()
    try:
        run = session.get(Run, uuid.UUID(str(job.args[0])))
        if run is None or run.status not in {RunStatus.QUEUED, RunStatus.RUNNING}:
            return
        run.status = RunStatus.FAILED
        run.finished_at = datetime.now(UTC)
        run.error_summary = reason[:2000]
        for stage in run.stages:
            if stage.status == RunStageStatus.RUNNING:
                stage.status = RunStageStatus.FAILED
                stage.error_type = "WorkerFailure"
                stage.error_message = reason[:2000]
                stage.finished_at = run.finished_at
            elif stage.status == RunStageStatus.PENDING:
                stage.status = RunStageStatus.SKIPPED
                stage.finished_at = run.finished_at
        session.commit()
    finally:
        remove_session()


def job_failed(job, connection, exc_type, exc_value, traceback):
    _mark_failed(job, f"Worker job failed: {exc_type.__name__}: {exc_value}")


def work_horse_killed(job, retpid, ret_val, rusage):
    _mark_failed(job, f"Worker execution process exited unexpectedly (exit status {ret_val}).")
