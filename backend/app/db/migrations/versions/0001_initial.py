"""initial schema — brands, competitors, runs and pipeline tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(200), nullable=True),
        sa.Column("location_code", sa.Integer(), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "competitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_competitors_brand_id", "competitors", ["brand_id"])

    run_status = sa.Enum(
        "queued", "running", "succeeded", "partial", "failed",
        name="run_status", native_enum=False, length=20,
    )
    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", run_status, nullable=False, server_default="queued"),
        sa.Column("trigger", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("llm_provider", sa.String(50), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("progress", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("dataforseo_cost_usd", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("brand_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_runs_brand_id_created_at", "runs", ["brand_id", "created_at"])

    run_stage_status = sa.Enum(
        "pending", "running", "succeeded", "failed", "skipped",
        name="run_stage_status", native_enum=False, length=20,
    )
    op.create_table(
        "run_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("status", run_stage_status, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("output_summary", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_run_stages_run_id", "run_stages", ["run_id"])

    query_source = sa.Enum(
        "keyword_ideas", "people_also_ask", "llm_planner",
        name="query_source", native_enum=False, length=30,
    )
    op.create_table(
        "queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("source", query_source, nullable=False),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("search_volume", sa.Integer(), nullable=True),
        sa.Column("competition", sa.Float(), nullable=True),
        sa.Column("cpc", sa.Float(), nullable=True),
        sa.Column("keyword_difficulty", sa.Float(), nullable=True),
    )
    op.create_index("ix_queries_run_id", "queries", ["run_id"])

    visibility_channel = sa.Enum(
        "google_organic", "google_ai_overview", "llm_chatgpt", "llm_google_ai",
        name="visibility_channel", native_enum=False, length=30,
    )
    op.create_table(
        "visibility_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("queries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", visibility_channel, nullable=False),
        sa.Column("brand_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("brand_position", sa.Integer(), nullable=True),
        sa.Column("competitors_visible", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("cited_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("raw_ref", sa.String(255), nullable=True),
    )
    op.create_index("ix_visibility_observations_query_id", "visibility_observations", ["query_id"])

    op.create_table(
        "opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("queries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("components", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("explanation", sa.Text(), nullable=True),
    )
    op.create_index("ix_opportunities_run_id_score", "opportunities", ["run_id", "score"])

    recommendation_status = sa.Enum(
        "todo", "in_progress", "done", "dismissed",
        name="recommendation_status", native_enum=False, length=20,
    )
    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("target_query", sa.String(500), nullable=True),
        sa.Column("outline", postgresql.JSONB(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("effort", sa.String(20), nullable=True),
        sa.Column("status", recommendation_status, nullable=False, server_default="todo"),
    )
    op.create_index("ix_recommendations_run_id", "recommendations", ["run_id"])

    op.create_table(
        "api_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_api_cache_expires_at", "api_cache", ["expires_at"])


def downgrade() -> None:
    op.drop_table("api_cache")
    op.drop_index("ix_recommendations_run_id", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("ix_opportunities_run_id_score", table_name="opportunities")
    op.drop_table("opportunities")
    op.drop_index("ix_visibility_observations_query_id", table_name="visibility_observations")
    op.drop_table("visibility_observations")
    op.drop_index("ix_queries_run_id", table_name="queries")
    op.drop_table("queries")
    op.drop_index("ix_run_stages_run_id", table_name="run_stages")
    op.drop_table("run_stages")
    op.drop_index("ix_runs_brand_id_created_at", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_competitors_brand_id", table_name="competitors")
    op.drop_table("competitors")
    op.drop_table("brands")
