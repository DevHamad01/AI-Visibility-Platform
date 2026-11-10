"""Per-request X-Request-ID, trace id propagation and one JSON access-log line
per request, plus the generic HTTP metrics.
"""

from __future__ import annotations

import time
import uuid

import structlog
from flask import Flask, Response, g, request

from app.core.logging import get_logger
from app.core.metrics import http_request_duration_seconds, http_requests_total

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"


def register_middleware(app: Flask) -> None:
    @app.before_request
    def start_request() -> None:
        g.request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        g.trace_id = request.headers.get(TRACE_ID_HEADER) or g.request_id
        g.start_time = time.monotonic()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=g.request_id,
            trace_id=g.trace_id,
            method=request.method,
            path=request.path,
        )

    @app.after_request
    def finish_request(response: Response) -> Response:
        response.headers[REQUEST_ID_HEADER] = g.get("request_id", "unknown")
        duration = time.monotonic() - g.get("start_time", time.monotonic())
        route = request.url_rule.rule if request.url_rule else request.path
        http_requests_total.labels(request.method, route, response.status_code).inc()
        http_request_duration_seconds.labels(request.method, route).observe(duration)
        logger.info(
            "request_completed",
            status=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        return response

    @app.teardown_request
    def teardown(_exc: BaseException | None) -> None:
        structlog.contextvars.clear_contextvars()
