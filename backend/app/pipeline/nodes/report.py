"""Report: assembles the final summary and decides succeeded | partial |
failed (CLAUDE.md section 4):
  - failed: no queries were ever produced — there's nothing to show.
  - partial: at least one query exists, but some stage recorded an error
    (a retrieval call failed, an LLM stage failed, ...).
  - succeeded: queries exist and nothing failed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.core.metrics import runs_total
from app.db.models import Opportunity, Query, Recommendation, Run, RunStage, RunStageStatus, RunStatus
from app.pipeline.context import PipelineContext
from app.pipeline.stages import NodeResult
from app.pipeline.state import RunState


def report(ctx: PipelineContext, state: RunState) -> NodeResult:
    stage_errors = state.get("stage_errors") or {}
    sufficient_data = bool(state.get("sufficient_data", False))

    if not sufficient_data:
        status = RunStatus.FAILED
    elif stage_errors:
        status = RunStatus.PARTIAL
    else:
        status = RunStatus.SUCCEEDED

    run = ctx.session.get(Run, ctx.run_id)
    run.status = status
    run.finished_at = datetime.now(UTC)
    run.error_summary = "; ".join(f"{k}: {v}" for k, v in stage_errors.items()) or None

    stages = ctx.session.query(RunStage).filter(RunStage.run_id == ctx.run_id).all()
    succeeded_count = sum(1 for s in stages if s.status == RunStageStatus.SUCCEEDED)
    failed_count = sum(1 for s in stages if s.status == RunStageStatus.FAILED)
    total_duration_ms = sum(s.duration_ms or 0 for s in stages)

    query_planner_stage = next((s for s in stages if s.stage == "query_planner"), None)
    if query_planner_stage and query_planner_stage.output_summary:
        run.llm_provider = query_planner_stage.output_summary.get("provider")
        run.llm_model = query_planner_stage.output_summary.get("model")

    counts = {
        "queries": ctx.session.query(Query).filter(Query.run_id == ctx.run_id).count(),
        "opportunities": ctx.session.query(Opportunity).filter(Opportunity.run_id == ctx.run_id).count(),
        "recommendations": ctx.session.query(Recommendation)
        .filter(Recommendation.run_id == ctx.run_id)
        .count(),
    }

    run.metrics = {
        "total_duration_ms": total_duration_ms,
        "stages_succeeded": succeeded_count,
        "stages_failed": failed_count,
        "dataforseo_cost_usd": round(ctx.budget.spent_usd, 6),
        **counts,
    }
    run.dataforseo_cost_usd = Decimal(str(round(ctx.budget.spent_usd, 6)))
    run.progress = {
        "stages_total": len(stages),
        "stages_succeeded": succeeded_count,
        "stages_failed": failed_count,
    }
    ctx.session.commit()

    runs_total.labels(status.value).inc()

    return NodeResult(
        state_update={"report": run.metrics},
        output_summary={"status": status.value, **run.metrics},
    )
