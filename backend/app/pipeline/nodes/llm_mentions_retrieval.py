"""LlmMentionsRetrieval: executes the single `llm_mentions_search` tool call
from QueryPlanner (QueryPlanner already capped this to at most one; this
node just executes it — CLAUDE.md section 4).

This is DataForSEO's most expensive endpoint and, on a trial account, the
one most likely to be gated by plan/auth. Per CLAUDE.md: "If an endpoint
returns an auth/plan error ... that tool's stage is failed with a clear
reason; the run continues and ends partial." — so here, unlike the other
two retrieval nodes, a failure is always a *stage* failure (there's only
ever one call, so partial success isn't possible).
"""

from __future__ import annotations

from app.pipeline.context import PipelineContext
from app.pipeline.stages import NodeResult
from app.pipeline.state import RunState
from app.tools.dataforseo.errors import ToolArgumentError
from app.tools.dataforseo.llm_mentions import llm_mentions_search


def llm_mentions_retrieval(ctx: PipelineContext, state: RunState) -> NodeResult:
    calls = [c for c in state.get("tool_calls") or [] if c["name"] == "llm_mentions_search"]
    if not calls:
        return NodeResult(state_update={"llm_mention_items": []}, output_summary={"calls_attempted": 0})

    call = calls[0]
    result = llm_mentions_search(ctx.df_client, call["arguments"])
    if isinstance(result, ToolArgumentError):
        return NodeResult(
            state_update={"llm_mention_items": []},
            output_summary={"calls_attempted": 1, "argument_error": result.errors},
        )

    items = [item.model_dump() for item in result.items]
    return NodeResult(
        state_update={"llm_mention_items": items},
        output_summary={"calls_attempted": 1, "items_returned": len(items), "cost": result.cost},
    )
