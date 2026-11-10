"""Prometheus metrics. Exposed at GET /metrics.

Node/dependency/run metrics listed in CLAUDE.md section 6 (node_duration_seconds,
external_calls_total, circuit_state, dataforseo_cost_usd_total, ...) are added in
Phase 2/3 alongside the code that produces them. Phase 1 only wires the registry
and the generic HTTP request metric.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the API.",
    labelnames=("method", "path", "status"),
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    labelnames=("method", "path"),
)


def render_latest() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
