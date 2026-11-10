"""/api/v1/brands — full CRUD on brands."""

from __future__ import annotations

from flask import Response
from flask_openapi3 import APIBlueprint, Tag
from sqlalchemy import select

from app.api.pagination import decode_cursor, paginate
from app.api.schemas import (
    BrandCreate,
    BrandListResponse,
    BrandPath,
    BrandResponse,
    BrandUpdate,
    ListQuery,
)
from app.core.errors import NotFoundError
from app.db.base import get_session
from app.db.models import Brand

tag = Tag(name="brands", description="Brand profiles under analysis.")
brands_bp = APIBlueprint("brands", __name__, url_prefix="/api/v1/brands", abp_tags=[tag])


def _get_brand_or_404(brand_id) -> Brand:
    brand = get_session().get(Brand, brand_id)
    if brand is None:
        raise NotFoundError(f"Brand {brand_id} does not exist.")
    return brand


@brands_bp.post("", responses={201: BrandResponse})
def create_brand(body: BrandCreate):
    session = get_session()
    brand = Brand(**body.model_dump())
    session.add(brand)
    session.commit()
    response = Response(
        BrandResponse.model_validate(brand).model_dump_json(), status=201, mimetype="application/json"
    )
    response.headers["Location"] = f"/api/v1/brands/{brand.id}"
    return response


@brands_bp.get("", responses={200: BrandListResponse})
def list_brands(query: ListQuery):
    session = get_session()
    stmt = select(Brand).order_by(Brand.created_at.asc(), Brand.id.asc())
    if query.cursor:
        created_at, id_ = decode_cursor(query.cursor)
        stmt = stmt.where(
            (Brand.created_at > created_at)
            | ((Brand.created_at == created_at) & (Brand.id > id_))
        )
    rows = list(session.execute(stmt.limit(query.limit + 1)).scalars())
    page, next_cursor = paginate(rows, query.limit)
    return BrandListResponse(
        items=[BrandResponse.model_validate(b) for b in page], next_cursor=next_cursor
    ).model_dump(mode="json")


@brands_bp.get("/<string:brand_id>", responses={200: BrandResponse})
def get_brand(path: BrandPath):
    brand = _get_brand_or_404(path.brand_id)
    return BrandResponse.model_validate(brand).model_dump(mode="json")


@brands_bp.patch("/<string:brand_id>", responses={200: BrandResponse})
def update_brand(path: BrandPath, body: BrandUpdate):
    session = get_session()
    brand = _get_brand_or_404(path.brand_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(brand, field, value)
    session.commit()
    return BrandResponse.model_validate(brand).model_dump(mode="json")


@brands_bp.delete("/<string:brand_id>", responses={204: None})
def delete_brand(path: BrandPath):
    session = get_session()
    brand = _get_brand_or_404(path.brand_id)
    session.delete(brand)
    session.commit()
    return "", 204


__all__ = ["brands_bp"]
