"""Common node wrapper: every pipeline node gets wrapped by `run_node`, which
logs start/end, updates its `run_stages` row, emits metrics, and — critically
— catches any exception so one node failing never stops the graph or
discards other branches' work (CLAUDE.md section 4).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.core.metrics import node_duration_seconds, node_runs_total
from app.db.models import RunStage, RunStageStatus
from app.pipeline.context import PipelineContext
from app.pipeline.state import RunState

logger = get_logger(__name__)

# Canonical order — also what gets pre-created as `pending` RunStage rows
# when a run starts, so the trace/progress view shows the full plan upfront.
STAGE_NAMES = [
    "query_planner",
    "keyword_retrieval",
    "serp_retrieval",
    "llm_mentions_retrieval",
    "normalizer",
    "opportunity_scorer",
    "gap_analyst",
    "recommender",
    "report",
]


@dataclass
class NodeResult:
    state_update: dict[str, Any]
    output_summary: dict[str, Any] = field(default_factory=dict)
    attempts: int | None = None


def create_pending_stages(ctx: PipelineContext) -> None:
    for name in STAGE_NAMES:
        ctx.session.add(RunStage(run_id=ctx.run_id, stage=name, status=RunStageStatus.PENDING))
    ctx.session.commit()


def _get_stage(ctx: PipelineContext, name: str) -> RunStage:
    stage = (
        ctx.session.query(RunStage)
        .filter(RunStage.run_id == ctx.run_id, RunStage.stage == name)
        .one()
    )
    return stage


def run_node(
    ctx: PipelineContext, name: str, fn: Callable[[RunState], NodeResult]
) -> Callable[[RunState], dict[str, Any]]:
    def wrapped(state: RunState) -> dict[str, Any]:
        stage = _get_stage(ctx, name)
        stage.status = RunStageStatus.RUNNING
        stage.attempts += 1
        stage.started_at = datetime.now(UTC)
        ctx.session.commit()
        logger.info("node_started", run_id=str(ctx.run_id), trace_id=ctx.trace_id, node=name)

        start = time.monotonic()
        try:
            result = fn(state)
        except Exception as exc:  # noqa: BLE001 — a node must never abort the graph
            duration_ms = int((time.monotonic() - start) * 1000)
            stage.status = RunStageStatus.FAILED
            stage.error_type = type(exc).__name__
            stage.error_message = str(exc)[:2000]
            stage.finished_at = datetime.now(UTC)
            stage.duration_ms = duration_ms
            ctx.session.commit()
            node_duration_seconds.labels(name).observe(duration_ms / 1000)
            node_runs_total.labels(name, "failed").inc()
            logger.warning(
                "node_failed",
                run_id=str(ctx.run_id),
                trace_id=ctx.trace_id,
                node=name,
                error_type=type(exc).__name__,
                duration_ms=duration_ms,
            )
            merged_errors = dict(state.get("stage_errors") or {})
            merged_errors[name] = f"{type(exc).__name__}: {exc}"
            return {"stage_errors": merged_errors}

        duration_ms = int((time.monotonic() - start) * 1000)
        stage.status = RunStageStatus.SUCCEEDED
        if result.attempts is not None:
            stage.attempts = result.attempts
        stage.output_summary = result.output_summary
        stage.finished_at = datetime.now(UTC)
        stage.duration_ms = duration_ms
        ctx.session.commit()
        node_duration_seconds.labels(name).observe(duration_ms / 1000)
        node_runs_total.labels(name, "succeeded").inc()
        logger.info(
            "node_succeeded",
            run_id=str(ctx.run_id),
            trace_id=ctx.trace_id,
            node=name,
            duration_ms=duration_ms,
        )
        return result.state_update

    return wrapped
