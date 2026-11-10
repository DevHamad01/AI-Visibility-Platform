"""Liveness/readiness/metrics endpoints. Not part of the versioned, documented
API — infra probes don't need a schema or Swagger entry."""

from __future__ import annotations

from flask import Blueprint, Response, current_app

from app.core.logging import get_logger
from app.core.metrics import render_latest
from app.db.base import get_engine

logger = get_logger(__name__)

health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def healthz() -> tuple[dict, int]:
    return {"status": "ok"}, 200


@health_bp.get("/readyz")
def readyz() -> tuple[dict, int]:
    checks: dict[str, str] = {}
    healthy = True

    try:
        with get_engine().connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 — readiness probe must never raise
        healthy = False
        checks["database"] = f"error: {exc}"

    try:
        redis_client = current_app.extensions["redis"]
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        healthy = False
        checks["redis"] = f"error: {exc}"

    status_code = 200 if healthy else 503
    if not healthy:
        logger.warning("readiness_check_failed", checks=checks)
    return {"status": "ok" if healthy else "unavailable", "checks": checks}, status_code


@health_bp.get("/metrics")
def metrics() -> Response:
    body, content_type = render_latest()
    return Response(body, mimetype=content_type)
