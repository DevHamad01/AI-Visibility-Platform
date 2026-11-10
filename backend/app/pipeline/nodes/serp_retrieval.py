"""SerpRetrieval: executes the validated `serp_google_organic` tool call(s)
from QueryPlanner. Only calls the API, no reasoning (CLAUDE.md section 4).
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
from app.tools.dataforseo.serp_google_organic import serp_google_organic

logger = get_logger(__name__)

_CALL_FAILURE_TYPES = (RetryableError, NonRetryableError, CircuitOpenError, BudgetExceededError)


def serp_retrieval(ctx: PipelineContext, state: RunState) -> NodeResult:
    if ctx.settings.demo_fail_serp:
        raise StageFailedError("Simulated SERP dependency outage (DEMO_FAIL_SERP=true).")
    calls = [c for c in state.get("tool_calls") or [] if c["name"] == "serp_google_organic"]
    entries: list[dict] = []
    errors: list[str] = []

    for call in calls:
        query_text = call["arguments"].get("keyword", "")
        try:
            result = serp_google_organic(ctx.df_client, call["arguments"])
        except _CALL_FAILURE_TYPES as exc:
            errors.append(f"{query_text!r}: {type(exc).__name__}: {exc}")
            logger.warning(
                "serp_retrieval_call_failed", run_id=str(ctx.run_id), query=query_text, error=str(exc)
            )
            continue

        if isinstance(result, ToolArgumentError):
            errors.append(f"{query_text!r}: ToolArgumentError: {result.errors}")
            continue

        entries.append({"query_text": query_text, "result": result.model_dump()})

    if calls and not entries and errors:
        raise StageFailedError("; ".join(errors))

    return NodeResult(
        state_update={"serp_entries": entries},
        output_summary={"calls_attempted": len(calls), "entries_returned": len(entries), "errors": errors},
        error_message="; ".join(errors) if errors else None,
    )
