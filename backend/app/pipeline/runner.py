"""Entry point the RQ worker calls: `app.pipeline.runner.execute_run(run_id)`.
Builds the run-scoped `PipelineContext` and runs the graph. A worker
crash/timeout never leaves a run stuck `running` forever — RQ's own
`job_timeout` (CLAUDE.md section 5) interrupts it, and the `except` below
always marks the run `failed` with a reason before giving up.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import get_engine, get_session, init_engine
from app.db.models import Run, RunStatus
from app.llm.client import LLMClient
from app.pipeline.context import PipelineContext
from app.pipeline.graph import run_pipeline
from app.pipeline.stages import create_pending_stages
from app.tools.dataforseo.budget import RunBudget
from app.tools.dataforseo.client import DataForSEOClient

logger = get_logger(__name__)


def _ensure_engine() -> None:
    try:
        get_engine()
    except RuntimeError:
        init_engine(get_settings().database_url)


def execute_run(run_id: str) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    _ensure_engine()

    run_uuid = uuid.UUID(run_id)
    session = get_session()
    run = session.get(Run, run_uuid)
    if run is None:
        logger.error("run_not_found", run_id=run_id)
        return

    structlog.contextvars.bind_contextvars(run_id=run_id, trace_id=run.trace_id or run_id)
    try:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        session.commit()

        budget = RunBudget(max_cost_usd=settings.dataforseo_max_cost_per_run)
        ctx = PipelineContext(
            run_id=run_uuid,
            brand_id=run.brand_id,
            trace_id=run.trace_id or run_id,
            brand_snapshot=run.brand_snapshot,
            settings=settings,
            df_client=DataForSEOClient(settings, budget=budget),
            llm_client=LLMClient(settings),
            budget=budget,
        )
        create_pending_stages(ctx)
        logger.info("run_started", brand_id=str(run.brand_id))
        run_pipeline(ctx)
        logger.info("run_finished")
    except Exception as exc:  # noqa: BLE001 — last-resort guard; nodes already catch their own
        logger.error("run_crashed", error=str(exc), error_type=type(exc).__name__)
        failed_run = session.get(Run, run_uuid)
        if failed_run is not None and failed_run.status not in (
            RunStatus.SUCCEEDED,
            RunStatus.PARTIAL,
            RunStatus.FAILED,
        ):
            failed_run.status = RunStatus.FAILED
            failed_run.finished_at = datetime.now(UTC)
            failed_run.error_summary = f"{type(exc).__name__}: {exc}"
            session.commit()
    finally:
        structlog.contextvars.clear_contextvars()
