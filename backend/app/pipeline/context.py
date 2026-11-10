"""Run-scoped dependencies every pipeline node closes over. Built once per
run by the worker job and threaded into each node via a factory function —
simpler to read and debug than passing dependencies through LangGraph's own
`config` mechanism for a graph this size.

`session` is a *property*, not a stored field: LangGraph runs the three
parallel retrieval branches (KeywordRetrieval/SerpRetrieval/
LlmMentionsRetrieval) on separate threads, and a single SQLAlchemy `Session`
is not safe to share across threads. `get_session()` is backed by a
`scoped_session`, keyed by thread identity, so each thread transparently
gets its own session — the sequential nodes still see one consistent
session throughout (same thread, same scoped-session lookup), and the
parallel ones stop colliding.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import get_session
from app.llm.client import LLMClient
from app.tools.dataforseo.budget import RunBudget
from app.tools.dataforseo.client import DataForSEOClient


@dataclass
class PipelineContext:
    run_id: uuid.UUID
    brand_id: uuid.UUID
    trace_id: str
    brand_snapshot: dict
    settings: Settings
    df_client: DataForSEOClient
    llm_client: LLMClient
    budget: RunBudget

    @property
    def session(self) -> Session:
        return get_session()
