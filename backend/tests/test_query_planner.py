"""QueryPlanner: a malformed or out-of-range tool call from the LLM is
dropped before it ever reaches a retrieval node (CLAUDE.md section 4:
"invalid/partial args → dropped + logged, never executed"), and the
budget-critical caps (<=1 keyword_ideas, <=1 llm_mentions_search, <=N
serp_google_organic) are enforced in code regardless of what the LLM
proposed."""

from __future__ import annotations

import json

import httpx
import respx

from app.pipeline.nodes.query_planner import query_planner

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _tool_calls_response(tool_calls: list[dict]) -> dict:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
            }
            for i, tc in enumerate(tool_calls)
        ],
    }
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls"}],
    }


class _FakePipelineContext:
    def __init__(self, llm_client, settings, brand_snapshot):
        self.llm_client = llm_client
        self.settings = settings
        self.brand_snapshot = brand_snapshot


@respx.mock
def test_malformed_and_unknown_tool_calls_are_dropped(resilient_settings):
    from app.llm.client import LLMClient

    proposed = [
        {
            "name": "keyword_ideas",
            "arguments": {"keywords": ["project management"], "location_code": 2840, "limit": 10},
        },
        {
            # out of range depth (max 200) — invalid, must be dropped
            "name": "serp_google_organic",
            "arguments": {"keyword": "best tool", "location_code": 2840, "depth": 999},
        },
        {
            # unknown tool name — must be dropped
            "name": "not_a_real_tool",
            "arguments": {"anything": 1},
        },
        {
            "name": "llm_mentions_search",
            "arguments": {"targets": [{"domain": "acme.com"}], "location_code": 2840},
        },
    ]
    respx.post(GROQ_URL).mock(return_value=httpx.Response(200, json=_tool_calls_response(proposed)))

    ctx = _FakePipelineContext(
        llm_client=LLMClient(resilient_settings),
        settings=resilient_settings,
        brand_snapshot={"name": "Acme", "domain": "acme.com", "competitors": []},
    )

    result = query_planner(ctx, {})

    kept_names = [c["name"] for c in result.state_update["tool_calls"]]
    assert kept_names == ["keyword_ideas", "llm_mentions_search"]
    # LLMClient.call_tools already drops the invalid-depth and unknown-tool
    # calls (Phase 2 behavior) before query_planner ever sees them — so only
    # the 2 valid calls show up here at all.
    assert result.output_summary["proposed_calls"] == 2
    assert result.output_summary["kept_calls"] == 2


@respx.mock
def test_caps_enforced_even_if_llm_proposes_more(resilient_settings):
    from app.llm.client import LLMClient

    keyword_idea_calls = [
        {"name": "keyword_ideas", "arguments": {"keywords": ["a"], "location_code": 2840}} for _ in range(3)
    ]
    llm_mentions_calls = [
        {
            "name": "llm_mentions_search",
            "arguments": {"targets": [{"domain": "acme.com"}], "location_code": 2840},
        }
        for _ in range(3)
    ]
    serp_calls = [
        {"name": "serp_google_organic", "arguments": {"keyword": f"query {i}", "location_code": 2840}}
        for i in range(20)
    ]
    proposed = (
        keyword_idea_calls
        + llm_mentions_calls
        + serp_calls
    )
    respx.post(GROQ_URL).mock(return_value=httpx.Response(200, json=_tool_calls_response(proposed)))

    settings = resilient_settings.model_copy(update={"max_serp_calls_per_run": 3})
    ctx = _FakePipelineContext(
        llm_client=LLMClient(settings),
        settings=settings,
        brand_snapshot={"name": "Acme", "domain": "acme.com", "competitors": []},
    )

    result = query_planner(ctx, {})
    by_tool = result.output_summary["by_tool"]
    assert by_tool["keyword_ideas"] == 1
    assert by_tool["llm_mentions_search"] == 1
    assert by_tool["serp_google_organic"] == 3
