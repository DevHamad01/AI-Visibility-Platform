"""Run-related endpoints (CLAUDE.md section 3): starting/listing runs, live
progress (SSE), results (visibility matrix, opportunities, recommendations),
comparing two runs, portfolio overview, export, and frontend error reports.
"""

from __future__ import annotations

import csv
import io
import json
import uuid

from flask import Response, current_app, request, stream_with_context
from flask_openapi3 import APIBlueprint, Tag
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.rate_limit import is_rate_limited
from app.api.run_schemas import (
    BrandOverview,
    ClientErrorReport,
    CompareQuery,
    CompareResponse,
    ExportQuery,
    OpportunitiesQuery,
    OpportunityDelta,
    OpportunityListResponse,
    OpportunityResponse,
    OverviewResponse,
    QueryVisibilityResponse,
    RecommendationListResponse,
    RecommendationResponse,
    RecommendationUpdate,
    RunListResponse,
    RunResponse,
    RunSummaryResponse,
    VisibilityMatrixResponse,
    VisibilityObservationResponse,
)
from app.api.schemas import ListQuery
from app.api.sse import run_events_stream
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ProblemError
from app.core.logging import get_logger
from app.db.base import get_session
from app.db.models import (
    Brand,
    Opportunity,
    Query,
    Recommendation,
    RecommendationStatus,
    Run,
    VisibilityObservation,
)
from app.services.run_service import RunAlreadyActiveError, create_run

logger = get_logger(__name__)

tag = Tag(name="runs", description="Analysis runs, results and recommendations.")
runs_bp = APIBlueprint("runs", __name__, url_prefix="/api/v1", abp_tags=[tag])


class BrandIdPath(BaseModel):
    brand_id: uuid.UUID


class RunIdPath(BaseModel):
    run_id: uuid.UUID


class RecommendationIdPath(BaseModel):
    recommendation_id: uuid.UUID


def _get_brand_or_404(brand_id: uuid.UUID) -> Brand:
    brand = get_session().get(Brand, brand_id)
    if brand is None:
        raise NotFoundError(f"Brand {brand_id} does not exist.")
    return brand


def _get_run_or_404(run_id: uuid.UUID) -> Run:
    run = get_session().get(Run, run_id)
    if run is None:
        raise NotFoundError(f"Run {run_id} does not exist.")
    return run


# --- create / list / detail / events ----------------------------------------


@runs_bp.post("/brands/<string:brand_id>/runs", responses={202: RunSummaryResponse, 409: None})
def create_run_endpoint(path: BrandIdPath):
    brand = _get_brand_or_404(path.brand_id)
    session = get_session()
    settings = get_settings()
    redis_client = current_app.extensions["redis"]
    idempotency_key = request.headers.get("Idempotency-Key")

    try:
        run, _created = create_run(session, redis_client, settings, brand, idempotency_key=idempotency_key)
    except RunAlreadyActiveError as exc:
        raise ConflictError(f"A run is already queued/running for this brand: {exc.run_id}") from exc

    response = Response(
        RunSummaryResponse.model_validate(run).model_dump_json(), status=202, mimetype="application/json"
    )
    response.headers["Location"] = f"/api/v1/runs/{run.id}"
    return response


@runs_bp.get("/brands/<string:brand_id>/runs", responses={200: RunListResponse})
def list_runs(path: BrandIdPath, query: ListQuery):
    _get_brand_or_404(path.brand_id)
    session = get_session()
    # Newest-first run history — small per brand, so we cap rather than
    # cursor-paginate (cursoring here would need a descending variant of
    # app.api.pagination's ascending (created_at, id) convention).
    rows = list(
        session.execute(
            select(Run)
            .where(Run.brand_id == path.brand_id)
            .order_by(Run.created_at.desc(), Run.id.desc())
            .limit(query.limit)
        ).scalars()
    )
    return RunListResponse(
        items=[RunSummaryResponse.model_validate(r) for r in rows], next_cursor=None
    ).model_dump(mode="json")


@runs_bp.get("/runs/<string:run_id>", responses={200: RunResponse})
def get_run(path: RunIdPath):
    run = _get_run_or_404(path.run_id)
    return RunResponse.model_validate(run).model_dump(mode="json")


@runs_bp.get("/runs/<string:run_id>/events")
def run_events(path: RunIdPath):
    _get_run_or_404(path.run_id)
    return Response(
        stream_with_context(run_events_stream(path.run_id)),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- results -----------------------------------------------------------------


@runs_bp.get("/runs/<string:run_id>/visibility", responses={200: VisibilityMatrixResponse})
def run_visibility(path: RunIdPath):
    run = _get_run_or_404(path.run_id)
    session = get_session()
    queries = session.execute(select(Query).where(Query.run_id == run.id).order_by(Query.id)).scalars().all()
    items = [
        QueryVisibilityResponse(
            id=q.id,
            text=q.text,
            source=q.source.value,
            intent=q.intent,
            search_volume=q.search_volume,
            observations=[
                VisibilityObservationResponse(
                    channel=o.channel.value,
                    brand_visible=o.brand_visible,
                    brand_position=o.brand_position,
                    competitors_visible=o.competitors_visible or [],
                    cited_urls=o.cited_urls or [],
                )
                for o in q.observations
            ],
        )
        for q in queries
    ]
    return VisibilityMatrixResponse(queries=items).model_dump(mode="json")


@runs_bp.get("/runs/<string:run_id>/opportunities", responses={200: OpportunityListResponse})
def run_opportunities(path: RunIdPath, query: OpportunitiesQuery):
    run = _get_run_or_404(path.run_id)
    session = get_session()
    stmt = (
        select(Opportunity).join(Query, Opportunity.query_id == Query.id).where(Opportunity.run_id == run.id)
    )
    if query.min_score is not None:
        stmt = stmt.where(Opportunity.score >= query.min_score)
    if query.intent is not None:
        stmt = stmt.where(Query.intent == query.intent)
    if query.q is not None:
        stmt = stmt.where(Query.text.ilike(f"%{query.q}%"))
    if query.channel is not None:
        # Filter before LIMIT; filtering a pre-limited list silently lost matches.
        stmt = stmt.where(Query.observations.any(VisibilityObservation.channel == query.channel))
    stmt = stmt.order_by(Opportunity.score.desc() if query.sort == "score_desc" else Opportunity.score.asc())
    rows = list(session.execute(stmt.limit(query.limit)).scalars())

    items = [
        OpportunityResponse(
            id=r.id,
            query_id=r.query_id,
            query_text=r.query.text,
            score=r.score,
            rank=r.rank,
            components=r.components,
            explanation=r.explanation,
        )
        for r in rows
    ]
    return OpportunityListResponse(items=items, next_cursor=None).model_dump(mode="json")


@runs_bp.get("/runs/<string:run_id>/recommendations", responses={200: RecommendationListResponse})
def run_recommendations(path: RunIdPath, query: ListQuery):
    run = _get_run_or_404(path.run_id)
    session = get_session()
    rows = list(
        session.execute(
            select(Recommendation)
            .where(Recommendation.run_id == run.id)
            .order_by(Recommendation.id)
            .limit(query.limit)
        ).scalars()
    )
    items = [RecommendationResponse.model_validate(r) for r in rows]
    return RecommendationListResponse(items=items, next_cursor=None).model_dump(mode="json")


@runs_bp.patch("/recommendations/<string:recommendation_id>", responses={200: RecommendationResponse})
def patch_recommendation(path: RecommendationIdPath, body: RecommendationUpdate):
    session = get_session()
    recommendation = session.get(Recommendation, path.recommendation_id)
    if recommendation is None:
        raise NotFoundError(f"Recommendation {path.recommendation_id} does not exist.")
    recommendation.status = RecommendationStatus(body.status)
    session.commit()
    return RecommendationResponse.model_validate(recommendation).model_dump(mode="json")


# --- compare / overview / export --------------------------------------------


@runs_bp.get("/brands/<string:brand_id>/compare", responses={200: CompareResponse})
def compare_runs(path: BrandIdPath, query: CompareQuery):
    _get_brand_or_404(path.brand_id)
    session = get_session()
    base_run = session.get(Run, query.base)
    target_run = session.get(Run, query.target)
    if base_run is None or base_run.brand_id != path.brand_id:
        raise NotFoundError(f"Run {query.base} does not exist for this brand.")
    if target_run is None or target_run.brand_id != path.brand_id:
        raise NotFoundError(f"Run {query.target} does not exist for this brand.")

    def _scores_by_text(run_id: uuid.UUID) -> dict[str, float]:
        stmt = (
            select(Opportunity)
            .join(Query, Opportunity.query_id == Query.id)
            .where(Opportunity.run_id == run_id)
        )
        rows = session.execute(stmt).scalars()
        return {row.query.text: row.score for row in rows}

    base_scores = _scores_by_text(query.base)
    target_scores = _scores_by_text(query.target)

    deltas: list[OpportunityDelta] = []
    for text in sorted(set(base_scores) | set(target_scores)):
        base_score = base_scores.get(text)
        target_score = target_scores.get(text)
        if base_score is not None and target_score is not None:
            delta = round(target_score - base_score, 2)
            # Opportunity score measures remaining gap — a LOWER score
            # between runs means visibility improved (less gap left).
            change = "declined" if delta > 0 else "improved" if delta < 0 else "unchanged"
        elif target_score is not None:
            delta, change = None, "new"
        else:
            delta, change = None, "dropped"
        deltas.append(
            OpportunityDelta(
                query_text=text, base_score=base_score, target_score=target_score, delta=delta, change=change
            )
        )

    return CompareResponse(base_run_id=query.base, target_run_id=query.target, deltas=deltas).model_dump(
        mode="json"
    )


@runs_bp.get("/overview", responses={200: OverviewResponse})
def overview():
    session = get_session()
    brands = session.execute(select(Brand).order_by(Brand.name)).scalars().all()
    items: list[BrandOverview] = []
    for brand in brands:
        latest_run = session.execute(
            select(Run).where(Run.brand_id == brand.id).order_by(Run.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        top_score = None
        opportunity_count = 0
        if latest_run is not None:
            top_opportunity = session.execute(
                select(Opportunity)
                .where(Opportunity.run_id == latest_run.id)
                .order_by(Opportunity.score.desc())
                .limit(1)
            ).scalar_one_or_none()
            top_score = top_opportunity.score if top_opportunity else None
            opportunity_count = session.execute(
                select(func.count()).select_from(Opportunity).where(Opportunity.run_id == latest_run.id)
            ).scalar_one()
        items.append(
            BrandOverview(
                brand_id=brand.id,
                brand_name=brand.name,
                latest_run_id=latest_run.id if latest_run else None,
                latest_run_status=latest_run.status.value if latest_run else None,
                latest_run_finished_at=latest_run.finished_at if latest_run else None,
                top_score=top_score,
                opportunity_count=opportunity_count,
            )
        )
    return OverviewResponse(brands=items).model_dump(mode="json")


@runs_bp.get("/runs/<string:run_id>/export")
def export_run(path: RunIdPath, query: ExportQuery):
    run = _get_run_or_404(path.run_id)
    session = get_session()
    opportunities = (
        session.execute(
            select(Opportunity)
            .join(Query, Opportunity.query_id == Query.id)
            .where(Opportunity.run_id == run.id)
            .order_by(Opportunity.rank)
        )
        .scalars()
        .all()
    )
    recommendations_by_opportunity: dict[uuid.UUID, list[Recommendation]] = {}
    for recommendation in session.execute(
        select(Recommendation).where(Recommendation.run_id == run.id)
    ).scalars():
        recommendations_by_opportunity.setdefault(recommendation.opportunity_id, []).append(recommendation)

    rows = [
        {
            "rank": opp.rank,
            "query": opp.query.text,
            "score": opp.score,
            "intent": opp.query.intent,
            "search_volume": opp.query.search_volume,
            "explanation": opp.explanation,
            "recommendations": "; ".join(r.title for r in recommendations_by_opportunity.get(opp.id, [])),
        }
        for opp in opportunities
    ]

    if query.format == "csv":
        buffer = io.StringIO()
        fieldnames = ["rank", "query", "score", "intent", "search_volume", "explanation", "recommendations"]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f'attachment; filename="run-{run.id}-export.csv"'
        return response

    return Response(
        json.dumps({"run_id": str(run.id), "opportunities": rows}, default=str), mimetype="application/json"
    )


# --- client errors -----------------------------------------------------------


@runs_bp.post("/client-errors", responses={202: None, 429: None})
def client_errors(body: ClientErrorReport):
    redis_client = current_app.extensions["redis"]
    rate_limit_key = f"ratelimit:client-errors:{request.remote_addr or 'unknown'}"
    if is_rate_limited(redis_client, rate_limit_key, limit=30, window_seconds=60):
        raise ProblemError(429, "Too Many Requests", "Client error reporting rate limit exceeded.")
    logger.warning(
        "frontend_error_reported", message=body.message, request_id=body.request_id, route=body.route
    )
    return "", 202


__all__ = ["runs_bp"]
