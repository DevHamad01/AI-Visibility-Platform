"""Pydantic request/response models for runs, visibility, opportunities,
recommendations, compare and overview (CLAUDE.md section 3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunStageResponse(BaseModel):
    stage: str
    status: str
    attempts: int
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    error_type: str | None
    error_message: str | None
    output_summary: dict[str, Any] | None

    model_config = {"from_attributes": True}


class RunSummaryResponse(BaseModel):
    """Without `stages` — used for list views, so listing many runs never
    triggers a per-run lazy-load of its stages."""

    id: uuid.UUID
    brand_id: uuid.UUID
    status: str
    trigger: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    llm_provider: str | None
    llm_model: str | None
    trace_id: str | None
    progress: dict[str, Any]
    metrics: dict[str, Any]
    error_summary: str | None
    dataforseo_cost_usd: float
    idempotency_key: str | None

    model_config = {"from_attributes": True}


class RunResponse(RunSummaryResponse):
    """The run detail view (GET /runs/{id}) — includes per-stage timing,
    attempts and errors, the "trace" view CLAUDE.md section 3 asks for."""

    stages: list[RunStageResponse] = Field(default_factory=list)


class RunListResponse(BaseModel):
    items: list[RunSummaryResponse]
    next_cursor: str | None


class VisibilityObservationResponse(BaseModel):
    channel: str
    brand_visible: bool
    brand_position: int | None
    competitors_visible: list[str]
    cited_urls: list[str]

    model_config = {"from_attributes": True}


class QueryVisibilityResponse(BaseModel):
    id: uuid.UUID
    text: str
    source: str
    intent: str | None
    search_volume: int | None
    observations: list[VisibilityObservationResponse]

    model_config = {"from_attributes": True}


class VisibilityMatrixResponse(BaseModel):
    queries: list[QueryVisibilityResponse]


class OpportunityResponse(BaseModel):
    id: uuid.UUID
    query_id: uuid.UUID
    query_text: str
    score: float
    rank: int
    components: dict[str, Any]
    explanation: str | None

    model_config = {"from_attributes": True}


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    next_cursor: str | None


class OpportunitiesQuery(BaseModel):
    min_score: float | None = Field(default=None, ge=0, le=100)
    channel: str | None = None
    intent: str | None = None
    q: str | None = None
    sort: Literal["score_desc", "score_asc"] = "score_desc"
    limit: int = Field(default=50, ge=1, le=200)


class RecommendationResponse(BaseModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID
    title: str
    content_type: str
    target_query: str | None
    outline: list[str] | None
    rationale: str | None
    priority: str | None
    effort: str | None
    status: str

    model_config = {"from_attributes": True}


class RecommendationListResponse(BaseModel):
    items: list[RecommendationResponse]
    next_cursor: str | None


class RecommendationUpdate(BaseModel):
    status: Literal["todo", "in_progress", "done", "dismissed"]


class CompareQuery(BaseModel):
    base: uuid.UUID
    target: uuid.UUID


class OpportunityDelta(BaseModel):
    query_text: str
    base_score: float | None
    target_score: float | None
    delta: float | None
    change: Literal["improved", "declined", "new", "dropped", "unchanged"]


class CompareResponse(BaseModel):
    base_run_id: uuid.UUID
    target_run_id: uuid.UUID
    deltas: list[OpportunityDelta]


class BrandOverview(BaseModel):
    brand_id: uuid.UUID
    brand_name: str
    latest_run_id: uuid.UUID | None
    latest_run_status: str | None
    latest_run_finished_at: datetime | None
    top_score: float | None
    opportunity_count: int


class OverviewResponse(BaseModel):
    brands: list[BrandOverview]


class ExportQuery(BaseModel):
    format: Literal["json", "csv"] = "json"


class ClientErrorReport(BaseModel):
    message: str = Field(..., max_length=2000)
    request_id: str | None = Field(default=None, max_length=100)
    route: str | None = Field(default=None, max_length=300)
    stack: str | None = Field(default=None, max_length=5000)
