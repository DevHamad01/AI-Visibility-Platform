"""The data threaded through the LangGraph DAG. Deliberately thin: every
node persists its own durable results straight to Postgres as it runs (so
partial work survives a later node failing), and only carries forward what
the next node actually needs — raw tool outputs, then just row ids.
"""

from __future__ import annotations

from typing import Any, TypedDict


class RunState(TypedDict, total=False):
    tool_calls: list[dict[str, Any]]
    keyword_idea_items: list[dict[str, Any]]
    serp_entries: list[dict[str, Any]]  # [{"query_text": str, "result": dict}]
    llm_mention_items: list[dict[str, Any]]
    stage_errors: dict[str, str]
    query_ids: list[str]
    sufficient_data: bool
    opportunity_ids: list[str]
    recommendation_ids: list[str]
    report: dict[str, Any]
