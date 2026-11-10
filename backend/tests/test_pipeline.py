"""Pipeline integration tests: a full happy-path run against mocked
DataForSEO + LLM HTTP, and a SERP-failure run proving partial results are
kept. The RQ job function (`app.pipeline.runner.execute_run`) is called
directly and synchronously — exactly what the worker does, just invoked
in-test instead of via a real worker process.
"""

from __future__ import annotations

import json
import re

import httpx
import respx

from app.db.base import get_session
from app.db.models import (
    Brand,
    Competitor,
    Opportunity,
    Query,
    Recommendation,
    RunStage,
    RunStageStatus,
    RunStatus,
)
from app.pipeline.runner import execute_run
from app.services.run_service import create_run

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DF_BASE = "https://api.dataforseo.com"


def _df_envelope(result: list[dict], cost: float = 0.01, status_code: int = 20000) -> dict:
    return {
        "status_code": status_code,
        "status_message": "Ok.",
        "cost": cost,
        "tasks": [{"status_code": status_code, "status_message": "Ok.", "cost": cost, "result": result}],
    }


def _chat_tool_calls_response(tool_calls: list[dict]) -> dict:
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


def _chat_content_response(content: dict) -> dict:
    message = {"role": "assistant", "content": json.dumps(content)}
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
    }


PLANNED_TOOL_CALLS = [
    {
        "name": "keyword_ideas",
        "arguments": {
            "keywords": ["project management", "task tracking"],
            "location_code": 2840,
            "language_code": "en",
            "limit": 10,
        },
    },
    {
        "name": "serp_google_organic",
        "arguments": {
            "keyword": "best project management software",
            "location_code": 2840,
            "language_code": "en",
            "depth": 10,
            "people_also_ask_click_depth": 1,
            "load_async_ai_overview": True,
        },
    },
    {
        "name": "serp_google_organic",
        "arguments": {
            "keyword": "acme vs monday",
            "location_code": 2840,
            "language_code": "en",
            "depth": 10,
        },
    },
    {
        "name": "llm_mentions_search",
        "arguments": {
            "targets": [{"domain": "acme.com"}, {"domain": "monday.com"}, {"domain": "asana.com"}],
            "platform": "google",
            "location_code": 2840,
            "language_code": "en",
            "limit": 10,
        },
    },
]


def _groq_side_effect(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if "tools" in body:
        return httpx.Response(200, json=_chat_tool_calls_response(PLANNED_TOOL_CALLS))

    system_content = body["messages"][0]["content"]
    user_content = body["messages"][1]["content"]
    query_ids = re.findall(r"query_id=['\"]([0-9a-fA-F-]{36})['\"]", user_content)

    if "search intent" in system_content:
        items = [
            {"query_id": qid, "intent": "commercial", "explanation": "Mocked explanation."}
            for qid in query_ids
        ]
        return httpx.Response(200, json=_chat_content_response({"items": items}))

    items = [
        {
            "query_id": qid,
            "title": "Mocked Content Title",
            "content_type": "blog_post",
            "outline": ["Intro", "Comparison", "CTA"],
            "rationale": "Mocked rationale.",
            "priority": "high",
            "effort": "medium",
        }
        for qid in query_ids
    ]
    return httpx.Response(200, json=_chat_content_response({"items": items}))


def _mock_keyword_ideas() -> respx.Route:
    return respx.post(f"{DF_BASE}/v3/dataforseo_labs/google/keyword_ideas/live").mock(
        return_value=httpx.Response(
            200,
            json=_df_envelope(
                [
                    {
                        "items": [
                            {
                                "keyword": "project management tool",
                                "keyword_info": {"search_volume": 8000, "competition": 0.4, "cpc": 2.5},
                                "keyword_properties": {"keyword_difficulty": 45},
                            },
                            {
                                "keyword": "task tracking software",
                                "keyword_info": {"search_volume": 3000, "competition": 0.2, "cpc": 1.1},
                                "keyword_properties": {"keyword_difficulty": 30},
                            },
                        ]
                    }
                ],
                cost=0.013,
            ),
        )
    )


def _mock_serp_calls() -> respx.Route:
    url = f"{DF_BASE}/v3/serp/google/organic/live/advanced"
    return respx.post(url).mock(
        side_effect=[
            httpx.Response(
                200,
                json=_df_envelope(
                    [
                        {
                            "items": [
                                {
                                    "type": "organic",
                                    "rank_absolute": 2,
                                    "domain": "acme.com",
                                    "title": "Acme — Project Management",
                                    "url": "https://acme.com",
                                },
                                {
                                    "type": "organic",
                                    "rank_absolute": 5,
                                    "domain": "monday.com",
                                    "title": "Monday.com",
                                    "url": "https://monday.com",
                                },
                                {
                                    "type": "ai_overview",
                                    "items": [{"url": "https://asana.com/guide"}],
                                },
                                {
                                    "type": "people_also_ask",
                                    "items": [{"title": "What is the best free project management tool?"}],
                                },
                            ]
                        }
                    ],
                    cost=0.002,
                ),
            ),
            httpx.Response(
                200,
                json=_df_envelope(
                    [
                        {
                            "items": [
                                {
                                    "type": "organic",
                                    "rank_absolute": 1,
                                    "domain": "monday.com",
                                    "title": "Monday.com",
                                    "url": "https://monday.com",
                                },
                            ]
                        }
                    ],
                    cost=0.002,
                ),
            ),
        ]
    )


def _mock_llm_mentions() -> respx.Route:
    url = f"{DF_BASE}/v3/ai_optimization/llm_mentions/search_mentions/live"
    return respx.post(url).mock(
        return_value=httpx.Response(
            200,
            json=_df_envelope(
                [
                    {
                        "items": [
                            {
                                "platform": "google",
                                "question": "which project management tool is best",
                                "answer": "Monday.com and Acme Corp are both popular options.",
                                "brand_entities": [
                                    {"title": "Monday.com", "position": 1, "category": "brand"},
                                    {"title": "Acme Corp", "position": 3, "category": "brand"},
                                ],
                                "sources": [{"url": "https://monday.com/compare"}],
                                "search_results": [],
                            }
                        ]
                    }
                ],
                cost=0.103,
            ),
        )
    )


def _make_brand_with_competitors() -> Brand:
    session = get_session()
    brand = Brand(name="Acme Corp", domain="acme.com", industry="project management software")
    session.add(brand)
    session.flush()
    session.add(Competitor(brand_id=brand.id, name="Monday.com", domain="monday.com"))
    session.add(Competitor(brand_id=brand.id, name="Asana", domain="asana.com"))
    session.commit()
    return brand


@respx.mock
def test_pipeline_happy_path_end_to_end(app, resilient_settings, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr("app.pipeline.runner.get_settings", lambda: resilient_settings)
    respx.post(GROQ_URL).mock(side_effect=_groq_side_effect)
    _mock_keyword_ideas()
    _mock_serp_calls()
    _mock_llm_mentions()

    brand = _make_brand_with_competitors()
    session = get_session()
    redis_client = __import__("redis").Redis.from_url(resilient_settings.redis_url)
    run, created = create_run(session, redis_client, resilient_settings, brand)
    assert created

    execute_run(str(run.id))

    session.refresh(run)
    assert run.status == RunStatus.SUCCEEDED, run.error_summary
    assert run.llm_provider == "groq"

    stages = session.query(RunStage).filter(RunStage.run_id == run.id).all()
    assert len(stages) == 9
    assert all(s.status == RunStageStatus.SUCCEEDED for s in stages), [
        (s.stage, s.status, s.error_message) for s in stages
    ]

    queries = session.query(Query).filter(Query.run_id == run.id).all()
    assert len(queries) == 6

    opportunities = session.query(Opportunity).filter(Opportunity.run_id == run.id).all()
    assert len(opportunities) == 6
    assert sorted(o.rank for o in opportunities) == [1, 2, 3, 4, 5, 6]
    top = next(o for o in opportunities if o.rank == 1)
    assert all(o.score <= top.score for o in opportunities)

    recommendations = session.query(Recommendation).filter(Recommendation.run_id == run.id).all()
    assert len(recommendations) >= 1
    assert all(r.title for r in recommendations)

    # The "acme vs monday" SERP call found no acme.com result — confirms the
    # domain-matching in Normalizer actually ran end-to-end, not just in
    # the scoring unit tests.
    gap_query = next(q for q in queries if q.text == "acme vs monday")
    organic_obs = next(o for o in gap_query.observations if o.channel.value == "google_organic")
    assert organic_obs.brand_visible is False
    assert "Monday.com" in organic_obs.competitors_visible

    assert resilient_settings  # keep fixture referenced for clarity


@respx.mock
def test_pipeline_serp_failure_ends_partial_and_keeps_other_work(app, resilient_settings, monkeypatch):  # noqa: ARG001
    monkeypatch.setattr("app.pipeline.runner.get_settings", lambda: resilient_settings)
    respx.post(GROQ_URL).mock(side_effect=_groq_side_effect)
    _mock_keyword_ideas()
    respx.post(f"{DF_BASE}/v3/serp/google/organic/live/advanced").mock(return_value=httpx.Response(503))
    _mock_llm_mentions()

    brand = _make_brand_with_competitors()
    session = get_session()
    redis_client = __import__("redis").Redis.from_url(resilient_settings.redis_url)
    run, _created = create_run(session, redis_client, resilient_settings, brand)

    execute_run(str(run.id))

    session.refresh(run)
    assert run.status == RunStatus.PARTIAL, run.error_summary
    assert "serp_retrieval" in (run.error_summary or "")

    stages = {s.stage: s for s in session.query(RunStage).filter(RunStage.run_id == run.id).all()}
    assert stages["serp_retrieval"].status == RunStageStatus.FAILED
    assert stages["keyword_retrieval"].status == RunStageStatus.SUCCEEDED
    assert stages["llm_mentions_retrieval"].status == RunStageStatus.SUCCEEDED
    assert stages["normalizer"].status == RunStageStatus.SUCCEEDED
    assert stages["opportunity_scorer"].status == RunStageStatus.SUCCEEDED

    # keyword_ideas (2) + llm_mentions (1) queries survive even though SERP failed entirely.
    queries = session.query(Query).filter(Query.run_id == run.id).all()
    assert len(queries) == 3
    opportunities = session.query(Opportunity).filter(Opportunity.run_id == run.id).all()
    assert len(opportunities) == 3
