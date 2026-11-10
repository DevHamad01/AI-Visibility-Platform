"""Each tool: argument validation happens before any HTTP call (invalid args
never reach the network), and happy-path responses parse into the typed
result. All HTTP mocked with respx — no real network."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.tools.dataforseo.client import DataForSEOClient
from app.tools.dataforseo.errors import ToolArgumentError
from app.tools.dataforseo.keyword_ideas import ENDPOINT as KEYWORD_IDEAS_ENDPOINT
from app.tools.dataforseo.keyword_ideas import keyword_ideas
from app.tools.dataforseo.llm_mentions import ENDPOINT as LLM_MENTIONS_ENDPOINT
from app.tools.dataforseo.llm_mentions import llm_mentions_search
from app.tools.dataforseo.search_volume import ENDPOINT as SEARCH_VOLUME_ENDPOINT
from app.tools.dataforseo.search_volume import search_volume
from app.tools.dataforseo.serp_google_organic import ENDPOINT as SERP_ENDPOINT
from app.tools.dataforseo.serp_google_organic import serp_google_organic


def _envelope(result: list[dict], cost: float = 0.001, status_code: int = 20000) -> dict:
    return {
        "status_code": status_code,
        "status_message": "Ok.",
        "cost": cost,
        "tasks": [{"status_code": status_code, "status_message": "Ok.", "cost": cost, "result": result}],
    }


@pytest.fixture()
def df_client(app, resilient_settings) -> DataForSEOClient:  # noqa: ARG001 — `app` wires up the DB
    return DataForSEOClient(resilient_settings)


# --- argument validation (no HTTP call at all) ------------------------------


@respx.mock
def test_keyword_ideas_missing_required_field_never_calls_http(df_client):
    route = respx.post(f"https://api.dataforseo.com{KEYWORD_IDEAS_ENDPOINT}")
    result = keyword_ideas(df_client, {"location_code": 2840})  # missing "keywords"
    assert isinstance(result, ToolArgumentError)
    assert result.tool == "keyword_ideas"
    assert not route.called


@respx.mock
def test_search_volume_wrong_type_never_calls_http(df_client):
    route = respx.post(f"https://api.dataforseo.com{SEARCH_VOLUME_ENDPOINT}")
    result = search_volume(df_client, {"keywords": "not-a-list", "location_code": 2840})
    assert isinstance(result, ToolArgumentError)
    assert not route.called


@respx.mock
def test_serp_organic_out_of_range_never_calls_http(df_client):
    route = respx.post(f"https://api.dataforseo.com{SERP_ENDPOINT}")
    result = serp_google_organic(
        df_client, {"keyword": "x", "location_code": 2840, "depth": 999}  # max is 200
    )
    assert isinstance(result, ToolArgumentError)
    assert not route.called


@respx.mock
def test_llm_mentions_missing_targets_never_calls_http(df_client):
    route = respx.post(f"https://api.dataforseo.com{LLM_MENTIONS_ENDPOINT}")
    result = llm_mentions_search(df_client, {"location_code": 2840})  # no "targets" at all
    assert isinstance(result, ToolArgumentError)
    assert not route.called


@respx.mock
def test_llm_mentions_more_than_ten_targets_never_calls_http(df_client):
    route = respx.post(f"https://api.dataforseo.com{LLM_MENTIONS_ENDPOINT}")
    result = llm_mentions_search(
        df_client,
        {
            "targets": [{"domain": f"competitor{i}.com"} for i in range(11)],
            "location_code": 2840,
        },
    )
    assert isinstance(result, ToolArgumentError)
    assert not route.called


# --- happy path ---------------------------------------------------------------


@respx.mock
def test_keyword_ideas_happy_path(df_client):
    respx.post(f"https://api.dataforseo.com{KEYWORD_IDEAS_ENDPOINT}").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "items": [
                            {
                                "keyword": "project management software",
                                "keyword_info": {
                                    "search_volume": 12000,
                                    "competition": 0.42,
                                    "competition_level": "MEDIUM",
                                    "cpc": 3.1,
                                },
                                "keyword_properties": {"keyword_difficulty": 55},
                            }
                        ]
                    }
                ],
                cost=0.0123,
            ),
        )
    )

    result = keyword_ideas(
        df_client, {"keywords": ["project management software"], "location_code": 2840}
    )

    assert not isinstance(result, ToolArgumentError)
    assert result.cost == 0.0123
    assert len(result.items) == 1
    idea = result.items[0]
    assert idea.keyword == "project management software"
    assert idea.search_volume == 12000
    assert idea.keyword_difficulty == 55


@respx.mock
def test_search_volume_happy_path(df_client):
    respx.post(f"https://api.dataforseo.com{SEARCH_VOLUME_ENDPOINT}").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "keyword": "buy laptop",
                        "search_volume": 9900,
                        "competition": "HIGH",
                        "competition_index": 87,
                        "cpc": 1.5,
                        "low_top_of_page_bid": 0.8,
                        "high_top_of_page_bid": 2.3,
                    }
                ]
            ),
        )
    )

    result = search_volume(df_client, {"keywords": ["buy laptop"], "location_code": 2840})

    assert not isinstance(result, ToolArgumentError)
    assert len(result.items) == 1
    item = result.items[0]
    assert item.keyword == "buy laptop"
    assert item.search_volume == 9900
    assert item.competition_index == 87


@respx.mock
def test_serp_google_organic_happy_path(df_client):
    respx.post(f"https://api.dataforseo.com{SERP_ENDPOINT}").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "items": [
                            {
                                "type": "organic",
                                "rank_absolute": 1,
                                "rank_group": 1,
                                "domain": "example.com",
                                "title": "Example",
                                "url": "https://example.com",
                                "description": "An example result.",
                            },
                            {
                                "type": "people_also_ask",
                                "items": [{"title": "What is project management?"}],
                            },
                            {
                                "type": "ai_overview",
                                "items": [{"url": "https://source.example.com/article"}],
                            },
                        ]
                    }
                ]
            ),
        )
    )

    result = serp_google_organic(df_client, {"keyword": "project management", "location_code": 2840})

    assert not isinstance(result, ToolArgumentError)
    assert len(result.organic_results) == 1
    assert result.organic_results[0].domain == "example.com"
    assert result.people_also_ask == ["What is project management?"]
    assert result.ai_overview_references == ["https://source.example.com/article"]


@respx.mock
def test_llm_mentions_happy_path(df_client):
    respx.post(f"https://api.dataforseo.com{LLM_MENTIONS_ENDPOINT}").mock(
        return_value=httpx.Response(
            200,
            json=_envelope(
                [
                    {
                        "items": [
                            {
                                "platform": "google",
                                "question": "best project management software",
                                "answer": "Some tools include Asana and Monday.com.",
                                "brand_entities": [
                                    {"title": "Asana", "position": 1, "category": "brand"},
                                    {"title": "Monday.com", "position": 2, "category": "brand"},
                                ],
                                "sources": [{"url": "https://asana.com"}],
                                "search_results": [],
                            }
                        ]
                    }
                ]
            ),
        )
    )

    result = llm_mentions_search(
        df_client,
        {
            "targets": [
                {"keyword": "project management software"},
                {"domain": "monday.com"},
            ],
            "location_code": 2840,
        },
    )

    assert not isinstance(result, ToolArgumentError)
    assert len(result.items) == 1
    item = result.items[0]
    assert item.platform == "google"
    assert [b.title for b in item.brand_entities] == ["Asana", "Monday.com"]
    assert item.source_urls == ["https://asana.com"]
