"""QueryPlanner: LLM tool-calling picks which DataForSEO tools to call and
with what arguments. `LLMClient.call_tools` already drops any call with an
unknown tool name or invalid/partial arguments (CLAUDE.md section 4).

On top of that, this node enforces the budget-critical caps in code, not
just in the prompt: at most one `keyword_ideas` call, at most
`MAX_SERP_CALLS_PER_RUN` distinct `serp_google_organic` calls, and — the
expensive one — at most **one** `llm_mentions_search` call per run, ever.
"""

from __future__ import annotations

from app.llm.types import ToolCall
from app.pipeline.context import PipelineContext
from app.pipeline.prompts import query_planner_system_prompt, query_planner_user_prompt
from app.pipeline.stages import NodeResult
from app.pipeline.state import RunState
from app.tools.dataforseo.keyword_ideas import TOOL_SPEC as KEYWORD_IDEAS_SPEC
from app.tools.dataforseo.llm_mentions import TOOL_SPEC as LLM_MENTIONS_SPEC
from app.tools.dataforseo.serp_google_organic import TOOL_SPEC as SERP_SPEC

TOOLS = [KEYWORD_IDEAS_SPEC, SERP_SPEC, LLM_MENTIONS_SPEC]


def _cap_calls(calls: list[ToolCall], ctx: PipelineContext) -> list[ToolCall]:
    kept: list[ToolCall] = []
    keyword_ideas_count = 0
    llm_mentions_count = 0
    serp_count = 0
    seen_serp_keywords: set[str] = set()

    for call in calls:
        if call.name == "keyword_ideas":
            if keyword_ideas_count >= 1:
                continue
            keyword_ideas_count += 1
            kept.append(call)
        elif call.name == "llm_mentions_search":
            if llm_mentions_count >= 1:
                continue
            llm_mentions_count += 1
            kept.append(call)
        elif call.name == "serp_google_organic":
            if serp_count >= ctx.settings.max_serp_calls_per_run:
                continue
            keyword_text = str(call.arguments.get("keyword", "")).strip().lower()
            if not keyword_text or keyword_text in seen_serp_keywords:
                continue
            seen_serp_keywords.add(keyword_text)
            serp_count += 1
            kept.append(call)
    return kept


def query_planner(ctx: PipelineContext, state: RunState) -> NodeResult:
    prompt = query_planner_user_prompt(
        ctx.brand_snapshot,
        max_queries=ctx.settings.max_queries_per_run,
        max_serp_calls=ctx.settings.max_serp_calls_per_run,
        location_code=ctx.brand_snapshot.get("location_code") or 2840,
        language_code=ctx.brand_snapshot.get("language_code") or "en",
    )
    result = ctx.llm_client.call_tools(prompt, TOOLS, system=query_planner_system_prompt())
    capped = _cap_calls(result.calls, ctx)

    output_summary = {
        "provider": result.provider,
        "model": result.model,
        "proposed_calls": len(result.calls),
        "kept_calls": len(capped),
        "by_tool": {
            name: sum(1 for c in capped if c.name == name)
            for name in ("keyword_ideas", "serp_google_organic", "llm_mentions_search")
        },
    }
    return NodeResult(
        state_update={"tool_calls": [{"name": c.name, "arguments": c.arguments} for c in capped]},
        output_summary=output_summary,
    )
