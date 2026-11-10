"""structlog setup: one JSON line per event on stdout, with request_id/trace_id
propagated via contextvars so every log line inside a request (or, from Phase 3,
inside a pipeline run) carries them automatically.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Keep stdlib logging (werkzeug, gunicorn, sqlalchemy) going through the
    # same JSON renderer instead of its own default formatter.
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(*args: object, **kwargs: object) -> structlog.types.FilteringBoundLogger:
    return structlog.get_logger(*args, **kwargs)
