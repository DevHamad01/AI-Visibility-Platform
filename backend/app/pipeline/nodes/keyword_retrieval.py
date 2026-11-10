"""KeywordRetrieval: executes the validated `keyword_ideas` tool call(s) from
QueryPlanner. Only calls the API, no reasoning (CLAUDE.md section 4).
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.resilience import CircuitOpenError, NonRetryableError, RetryableError
from app.pipeline.context import PipelineContext
from app.pipeline.errors import StageFailedError
from app.pipeline.stages import NodeResult
from app.pipeline.state import RunState
from app.tools.dataforseo.budget import BudgetExceededError
from app.tools.dataforseo.errors import ToolArgumentError
from app.tools.dataforseo.keyword_ideas import keyword_ideas

logger = get_logger(__name__)

_CALL_FAILURE_TYPES = (RetryableError, NonRetryableError, CircuitOpenError, BudgetExceededError)


def keyword_retrieval(ctx: PipelineContext, state: RunState) -> NodeResult:
    calls = [c for c in state.get("tool_calls") or [] if c["name"] == "keyword_ideas"]
    items: list[dict] = []
    errors: list[str] = []

    for call in calls:
        try:
            result = keyword_ideas(ctx.df_client, call["arguments"])
        except _CALL_FAILURE_TYPES as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            logger.warning("keyword_retrieval_call_failed", run_id=str(ctx.run_id), error=str(exc))
            continue

        if isinstance(result, ToolArgumentError):
            errors.append(f"ToolArgumentError: {result.errors}")
            continue

        items.extend(item.model_dump() for item in result.items)

    if calls and not items and errors:
        raise StageFailedError("; ".join(errors))

    return NodeResult(
        state_update={"keyword_idea_items": items},
        output_summary={"calls_attempted": len(calls), "items_returned": len(items), "errors": errors},
    )
