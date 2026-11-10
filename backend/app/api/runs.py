"""Run-related endpoints from CLAUDE.md section 3. The pipeline, worker and
scoring that back these are built in Phase 3 — for now every handler returns
a 501 `application/problem+json` response so the contract is visible in
Swagger (and callers get a typed, documented "not built yet" instead of a 404).
"""

from __future__ import annotations

import uuid

from flask_openapi3 import APIBlueprint, Tag
from pydantic import BaseModel

from app.core.errors import NotImplementedProblem

tag = Tag(name="runs", description="Analysis runs, results and recommendations (Phase 3).")
runs_bp = APIBlueprint("runs", __name__, url_prefix="/api/v1", abp_tags=[tag])


class BrandIdPath(BaseModel):
    brand_id: uuid.UUID


class RunIdPath(BaseModel):
    run_id: uuid.UUID


class RecommendationIdPath(BaseModel):
    recommendation_id: uuid.UUID


class CompareQuery(BaseModel):
    base: uuid.UUID
    target: uuid.UUID


class ExportQuery(BaseModel):
    format: str = "json"


def _not_built(what: str) -> NotImplementedProblem:
    return NotImplementedProblem(f"{what} is implemented in Phase 3 of this project.")


@runs_bp.post("/brands/<string:brand_id>/runs", responses={501: None})
def create_run(path: BrandIdPath):
    raise _not_built("Starting a run")


@runs_bp.get("/brands/<string:brand_id>/runs", responses={501: None})
def list_runs(path: BrandIdPath):
    raise _not_built("Run history")


@runs_bp.get("/runs/<string:run_id>", responses={501: None})
def get_run(path: RunIdPath):
    raise _not_built("Run status")


@runs_bp.get("/runs/<string:run_id>/events", responses={501: None})
def run_events(path: RunIdPath):
    raise _not_built("Live run events")


@runs_bp.get("/runs/<string:run_id>/visibility", responses={501: None})
def run_visibility(path: RunIdPath):
    raise _not_built("Visibility matrix")


@runs_bp.get("/runs/<string:run_id>/opportunities", responses={501: None})
def run_opportunities(path: RunIdPath):
    raise _not_built("Opportunities")


@runs_bp.get("/runs/<string:run_id>/recommendations", responses={501: None})
def run_recommendations(path: RunIdPath):
    raise _not_built("Recommendations")


@runs_bp.patch("/recommendations/<string:recommendation_id>", responses={501: None})
def patch_recommendation(path: RecommendationIdPath):
    raise _not_built("Updating a recommendation")


@runs_bp.get("/brands/<string:brand_id>/compare", responses={501: None})
def compare_runs(path: BrandIdPath, query: CompareQuery):
    raise _not_built("Comparing two runs")


@runs_bp.get("/overview", responses={501: None})
def overview():
    raise _not_built("Portfolio overview")


@runs_bp.get("/runs/<string:run_id>/export", responses={501: None})
def export_run(path: RunIdPath, query: ExportQuery):
    raise _not_built("Run export")


@runs_bp.post("/client-errors", responses={501: None})
def client_errors():
    raise _not_built("Frontend error reporting")


__all__ = ["runs_bp"]
