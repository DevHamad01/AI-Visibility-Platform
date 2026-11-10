"""Pydantic schemas for the LLM stages' structured output (GapAnalyst,
Recommender). Validated by LLMClient.complete_structured — never persisted
as-is; nodes map these onto ORM rows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GapAnalysisItem(BaseModel):
    query_id: str
    intent: Literal["informational", "commercial", "transactional", "navigational"]
    explanation: str = Field(..., max_length=500)


class GapAnalysisBatch(BaseModel):
    items: list[GapAnalysisItem]


class RecommendationItem(BaseModel):
    query_id: str
    title: str = Field(..., max_length=200)
    content_type: str = Field(..., max_length=100)
    outline: list[str] = Field(..., min_length=1, max_length=10)
    rationale: str = Field(..., max_length=500)
    priority: Literal["high", "medium", "low"]
    effort: Literal["low", "medium", "high"]


class RecommendationsBatch(BaseModel):
    items: list[RecommendationItem]
