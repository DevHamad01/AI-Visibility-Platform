"""RFC 7807 (application/problem+json) error handling.

Every error response — 404, 409, 422 validation, 500 — has the same shape:
{type, title, status, detail, instance, trace_id, errors[]}. 500s never leak
internals; the exception is logged with the trace id so it can be found later.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"


class ProblemError(Exception):
    """Raise anywhere in request handling to produce an RFC 7807 response."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str | None = None,
        type_: str = "about:blank",
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_
        self.errors = errors or []


class NotFoundError(ProblemError):
    def __init__(self, detail: str) -> None:
        super().__init__(404, "Not Found", detail, type_="https://httpstatuses.com/404")


class ConflictError(ProblemError):
    def __init__(self, detail: str) -> None:
        super().__init__(409, "Conflict", detail, type_="https://httpstatuses.com/409")


class NotImplementedProblem(ProblemError):
    def __init__(self, detail: str) -> None:
        super().__init__(501, "Not Implemented", detail, type_="https://httpstatuses.com/501")


def _trace_id() -> str:
    return getattr(g, "trace_id", getattr(g, "request_id", "unknown"))


def problem_response(
    status: int,
    title: str,
    detail: str | None = None,
    type_: str = "about:blank",
    errors: list[dict[str, Any]] | None = None,
) -> Response:
    body = {
        "type": type_,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.path,
        "trace_id": _trace_id(),
        "errors": errors or [],
    }
    response = jsonify(body)
    response.status_code = status
    response.content_type = PROBLEM_CONTENT_TYPE
    return response


def validation_error_callback(exc: ValidationError) -> Response:
    """Hooked into flask-openapi3 as validation_error_callback so request
    validation failures (path/query/body) come back as RFC 7807 too."""
    errors = [
        {
            "type": err.get("type"),
            "loc": list(err.get("loc", [])),
            "msg": err.get("msg"),
            "input": err.get("input"),
        }
        for err in exc.errors()
    ]
    return problem_response(
        422,
        "Validation Error",
        "The request did not match the expected schema.",
        type_="https://httpstatuses.com/422",
        errors=errors,
    )


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ProblemError)
    def handle_problem_error(exc: ProblemError) -> Response:
        return problem_response(exc.status, exc.title, exc.detail, exc.type_, exc.errors)

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException) -> Response:
        return problem_response(
            exc.code or 500,
            exc.name,
            exc.description,
            type_=f"https://httpstatuses.com/{exc.code}",
        )

    @app.errorhandler(Exception)
    def handle_unexpected_exception(exc: Exception) -> Response:
        logger.error("unhandled_exception", error=str(exc), exc_info=True)
        return problem_response(
            500,
            "Internal Server Error",
            "An unexpected error occurred. Reference the trace id when reporting this.",
            type_="https://httpstatuses.com/500",
        )
