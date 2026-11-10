"""/api/v1/brands/{brand_id}/competitors — competitors tracked for a brand."""

from __future__ import annotations

from flask import Response
from flask_openapi3 import APIBlueprint, Tag
from sqlalchemy import select

from app.api.pagination import decode_cursor, paginate
from app.api.schemas import (
    BrandPath,
    CompetitorCreate,
    CompetitorListResponse,
    CompetitorPath,
    CompetitorResponse,
    ListQuery,
)
from app.core.errors import NotFoundError
from app.db.base import get_session
from app.db.models import Brand, Competitor

tag = Tag(name="competitors", description="Competitors tracked for a brand.")
competitors_bp = APIBlueprint(
    "competitors", __name__, url_prefix="/api/v1/brands/<string:brand_id>/competitors", abp_tags=[tag]
)


def _get_brand_or_404(brand_id) -> Brand:
    brand = get_session().get(Brand, brand_id)
    if brand is None:
        raise NotFoundError(f"Brand {brand_id} does not exist.")
    return brand


def _get_competitor_or_404(brand_id, competitor_id) -> Competitor:
    competitor = get_session().get(Competitor, competitor_id)
    if competitor is None or competitor.brand_id != brand_id:
        raise NotFoundError(f"Competitor {competitor_id} does not exist for brand {brand_id}.")
    return competitor


@competitors_bp.post("", responses={201: CompetitorResponse})
def create_competitor(path: BrandPath, body: CompetitorCreate):
    session = get_session()
    _get_brand_or_404(path.brand_id)
    competitor = Competitor(brand_id=path.brand_id, **body.model_dump())
    session.add(competitor)
    session.commit()
    response = Response(
        CompetitorResponse.model_validate(competitor).model_dump_json(),
        status=201,
        mimetype="application/json",
    )
    response.headers["Location"] = f"/api/v1/brands/{path.brand_id}/competitors/{competitor.id}"
    return response


@competitors_bp.get("", responses={200: CompetitorListResponse})
def list_competitors(path: BrandPath, query: ListQuery):
    session = get_session()
    _get_brand_or_404(path.brand_id)
    stmt = (
        select(Competitor)
        .where(Competitor.brand_id == path.brand_id)
        .order_by(Competitor.created_at.asc(), Competitor.id.asc())
    )
    if query.cursor:
        created_at, id_ = decode_cursor(query.cursor)
        stmt = stmt.where(
            (Competitor.created_at > created_at)
            | ((Competitor.created_at == created_at) & (Competitor.id > id_))
        )
    rows = list(session.execute(stmt.limit(query.limit + 1)).scalars())
    page, next_cursor = paginate(rows, query.limit)
    return CompetitorListResponse(
        items=[CompetitorResponse.model_validate(c) for c in page], next_cursor=next_cursor
    ).model_dump(mode="json")


@competitors_bp.delete("/<string:competitor_id>", responses={204: None})
def delete_competitor(path: CompetitorPath):
    session = get_session()
    _get_brand_or_404(path.brand_id)
    competitor = _get_competitor_or_404(path.brand_id, path.competitor_id)
    session.delete(competitor)
    session.commit()
    return "", 204


__all__ = ["competitors_bp"]
