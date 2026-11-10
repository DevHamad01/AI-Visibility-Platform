"""Prometheus metrics. Exposed at GET /metrics.

Node-level pipeline metrics (node_duration_seconds, node_runs_total, runs_total)
are added in Phase 3 alongside the pipeline that produces them. This module
carries the generic HTTP metric (Phase 1) and the external-dependency metrics
used by every DataForSEO/LLM call from Phase 2 onward (CLAUDE.md section 6).
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Gauge, Histogram, generate_latest

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

external_calls_total = Counter(
    "external_calls_total",
    "Calls to an external dependency (DataForSEO, an LLM provider), by outcome.",
    labelnames=("dependency", "endpoint", "status"),
)

external_retries_total = Counter(
    "external_retries_total",
    "Retry attempts made against an external dependency beyond the first try.",
    labelnames=("dependency", "endpoint"),
)

circuit_state = Gauge(
    "circuit_state",
    "Circuit breaker state per dependency (0=closed/half-open, 1=open).",
    labelnames=("dependency",),
)

dataforseo_cost_usd_total = Counter(
    "dataforseo_cost_usd_total",
    "Cumulative DataForSEO cost in USD, as reported by each response.",
    labelnames=("endpoint",),
)

llm_fallbacks_total = Counter(
    "llm_fallbacks_total",
    "Times the LLM chain fell through from one provider to the next.",
    labelnames=("from_provider", "to_provider"),
)

api_cache_hits_total = Counter(
    "api_cache_hits_total",
    "DataForSEO response cache hits/misses by endpoint.",
    labelnames=("endpoint", "result"),
)


def render_latest() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
