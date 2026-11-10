"""The data threaded through the LangGraph DAG. Deliberately thin: every
node persists its own durable results straight to Postgres as it runs (so
partial work survives a later node failing), and only carries forward what
the next node actually needs — raw tool outputs, then just row ids.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def _merge_stage_errors(current: dict[str, str] | None, update: dict[str, str] | None) -> dict[str, str]:
    """Reducer for `stage_errors`: keyword_retrieval, serp_retrieval and
    llm_mentions_retrieval run in the same parallel superstep, and the
    `run_node` wrapper writes this key whichever of them fails. Without a
    reducer, two writes to the same key in one step is an `InvalidUpdateError`
    that crashes the whole run — discarding every stage's work, not just the
    failed ones, which breaks the "a node failing never discards other
    branches' work" contract this pipeline is built on. Plain `dict.update`
    is enough: branches never share a stage name, so there is never a real
    conflict to resolve, only different keys to combine.
    """
    merged = dict(current or {})
    merged.update(update or {})
    return merged


class RunState(TypedDict, total=False):
    tool_calls: list[dict[str, Any]]
    keyword_idea_items: list[dict[str, Any]]
    serp_entries: list[dict[str, Any]]  # [{"query_text": str, "result": dict}]
    llm_mention_items: list[dict[str, Any]]
    stage_errors: Annotated[dict[str, str], _merge_stage_errors]
    query_ids: list[str]
    sufficient_data: bool
    opportunity_ids: list[str]
    recommendation_ids: list[str]
    report: dict[str, Any]
