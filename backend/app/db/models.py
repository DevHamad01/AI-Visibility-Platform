"""SQLAlchemy models for every table in CLAUDE.md section 2.

A run is never overwritten: re-measuring a brand creates a new `Run` row, with
a `brand_snapshot` capturing the brand + competitors as they were at run time,
so history stays accurate even if the brand is edited later.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"


class RunStageStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class QuerySource(str, enum.Enum):
    KEYWORD_IDEAS = "keyword_ideas"
    PEOPLE_ALSO_ASK = "people_also_ask"
    LLM_PLANNER = "llm_planner"


class VisibilityChannel(str, enum.Enum):
    GOOGLE_ORGANIC = "google_organic"
    GOOGLE_AI_OVERVIEW = "google_ai_overview"
    LLM_CHATGPT = "llm_chatgpt"
    LLM_GOOGLE_AI = "llm_google_ai"


class RecommendationStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DISMISSED = "dismissed"


def _enum(e: type[enum.Enum]) -> SAEnum:
    return SAEnum(e, values_callable=lambda x: [m.value for m in x], native_enum=False)


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location_code: Mapped[int | None] = mapped_column(nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    competitors: Mapped[list[Competitor]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )
    runs: Mapped[list[Run]] = relationship(back_populates="brand", cascade="all, delete-orphan")


class Competitor(Base):
    __tablename__ = "competitors"
    __table_args__ = (Index("ix_competitors_brand_id", "brand_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brand: Mapped[Brand] = relationship(back_populates="competitors")


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (Index("ix_runs_brand_id_created_at", "brand_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        _enum(RunStatus), nullable=False, default=RunStatus.QUEUED
    )
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dataforseo_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    brand: Mapped[Brand] = relationship(back_populates="runs")
    stages: Mapped[list[RunStage]] = relationship(back_populates="run", cascade="all, delete-orphan")
    queries: Mapped[list[Query]] = relationship(back_populates="run", cascade="all, delete-orphan")
    opportunities: Mapped[list[Opportunity]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class RunStage(Base):
    __tablename__ = "run_stages"
    __table_args__ = (Index("ix_run_stages_run_id", "run_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[RunStageStatus] = mapped_column(
        _enum(RunStageStatus), nullable=False, default=RunStageStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    run: Mapped[Run] = relationship(back_populates="stages")


class Query(Base):
    __tablename__ = "queries"
    __table_args__ = (Index("ix_queries_run_id", "run_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[QuerySource] = mapped_column(_enum(QuerySource), nullable=False)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    search_volume: Mapped[int | None] = mapped_column(nullable=True)
    competition: Mapped[float | None] = mapped_column(nullable=True)
    cpc: Mapped[float | None] = mapped_column(nullable=True)
    keyword_difficulty: Mapped[float | None] = mapped_column(nullable=True)

    run: Mapped[Run] = relationship(back_populates="queries")
    observations: Mapped[list[VisibilityObservation]] = relationship(
        back_populates="query", cascade="all, delete-orphan"
    )
    opportunities: Mapped[list[Opportunity]] = relationship(back_populates="query")


class VisibilityObservation(Base):
    __tablename__ = "visibility_observations"
    __table_args__ = (Index("ix_visibility_observations_query_id", "query_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[VisibilityChannel] = mapped_column(_enum(VisibilityChannel), nullable=False)
    brand_visible: Mapped[bool] = mapped_column(nullable=False, default=False)
    brand_position: Mapped[int | None] = mapped_column(nullable=True)
    competitors_visible: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    cited_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)

    query: Mapped[Query] = relationship(back_populates="observations")


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (Index("ix_opportunities_run_id_score", "run_id", "score"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(back_populates="opportunities")
    query: Mapped[Query] = relationship(back_populates="opportunities")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="opportunity")


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (Index("ix_recommendations_run_id", "run_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_query: Mapped[str | None] = mapped_column(String(500), nullable=True)
    outline: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effort: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[RecommendationStatus] = mapped_column(
        _enum(RecommendationStatus), nullable=False, default=RecommendationStatus.TODO
    )

    run: Mapped[Run] = relationship(back_populates="recommendations")
    opportunity: Mapped[Opportunity] = relationship(back_populates="recommendations")


class ApiCache(Base):
    __tablename__ = "api_cache"
    __table_args__ = (Index("ix_api_cache_expires_at", "expires_at"),)

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cost: Mapped[float] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
