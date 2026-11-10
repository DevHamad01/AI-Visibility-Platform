"""Low-level DataForSEO v3 client: one `post()` used by every tool module.

Handles Basic auth, timeouts, retry/circuit-breaker (via app.core.resilience),
the Postgres-backed response cache (api_cache table), and cost metrics.
DataForSEO returns HTTP 200 for most logical errors, with the real outcome
in an inner `tasks[0].status_code` — classified here, not left to callers.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.metrics import api_cache_hits_total, dataforseo_cost_usd_total
from app.core.resilience import (
    CircuitBreaker,
    NonRetryableError,
    RetryableError,
    RetryPolicy,
    call_with_retry,
    get_circuit_breaker,
)
from app.db.base import get_session
from app.db.models import ApiCache
from app.tools.dataforseo.budget import RunBudget

logger = get_logger(__name__)

# HTTP-level: DataForSEO's documented codes are 401 (auth)/402 (balance)/
# 404 (bad path)/500; we also treat the usual gateway/rate-limit codes as
# retryable defensively, in case of transient infra in front of their API.
_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}

# Inner `status_code` (tasks[0].status_code) — DataForSEO returns HTTP 200
# even for most of these. 20000 and 40102 ("no matching results") are both
# successful outcomes (the latter just means an empty result set).
_OK_INNER_STATUS = {20000, 40102}
_RETRYABLE_INNER_STATUS = {40202, 50000, 50401}  # rate limited / system error / timeout


class DataForSEOStatusError(Exception):
    def __init__(self, status_code: int | None, status_message: str | None) -> None:
        super().__init__(f"DataForSEO status {status_code}: {status_message}")
        self.status_code = status_code
        self.status_message = status_message


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def cache_key(endpoint: str, payload: Any) -> str:
    raw = f"{endpoint}:{canonical_json(payload)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _retry_after_seconds(headers: httpx.Headers) -> float | None:
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _classify_inner_status(status_code: int | None) -> str:
    """Returns 'ok', 'retryable', or 'non_retryable'."""
    if status_code in _OK_INNER_STATUS:
        return "ok"
    if status_code in _RETRYABLE_INNER_STATUS:
        return "retryable"
    if status_code is not None and status_code >= 50000:
        return "retryable"
    return "non_retryable"


class DataForSEOClient:
    def __init__(self, settings: Settings, budget: RunBudget | None = None) -> None:
        self._settings = settings
        self._budget = budget
        self._circuit: CircuitBreaker = get_circuit_breaker(
            "dataforseo",
            settings.circuit_breaker_failure_threshold,
            settings.circuit_breaker_cooldown_seconds,
        )
        self._policy = RetryPolicy(
            max_attempts=settings.retry_max_attempts,
            backoff_base_seconds=settings.retry_backoff_base_seconds,
            backoff_max_seconds=settings.retry_backoff_max_seconds,
        )

    def post(
        self, endpoint: str, payload: list[dict[str, Any]], *, estimated_cost: float = 0.0
    ) -> dict[str, Any]:
        """`endpoint` is a path like '/v3/serp/google/organic/live/advanced'.
        Returns the first task's dict (status_code, status_message, cost,
        result). Raises DataForSEOStatusError / NonRetryableError / the last
        RetryableError / CircuitOpenError / BudgetExceededError on failure.

        `estimated_cost` (from app.tools.dataforseo.pricing) is checked
        against the run budget *before* any HTTP call — a cache hit is
        always free regardless of budget, since it costs nothing."""
        # Sandbox and live responses must never share a cache entry.
        key = cache_key(f"{self._settings.dataforseo_base_url.rstrip('/')}{endpoint}", payload)
        cached = self._get_cached(key)
        if cached is not None:
            api_cache_hits_total.labels(endpoint, "hit").inc()
            logger.info("dataforseo_cache_hit", endpoint=endpoint, cache_key=key[:12])
            return cached
        api_cache_hits_total.labels(endpoint, "miss").inc()

        task = call_with_retry(
            lambda: self._budgeted_post(endpoint, payload, estimated_cost),
            dependency="dataforseo",
            endpoint=endpoint,
            policy=self._policy,
            circuit=self._circuit,
        )
        self._set_cached(key, endpoint, task)
        return task

    def _budgeted_post(
        self, endpoint: str, payload: list[dict[str, Any]], estimated_cost: float
    ) -> dict[str, Any]:
        reservation = self._budget.reserve(endpoint, estimated_cost) if self._budget else nullcontext()
        with reservation:
            return self._do_post(endpoint, payload)

    def get_user_data(self) -> dict[str, Any]:
        """GET /v3/appendix/user_data — account balance/rate-limits. Never
        billed, never cached (we always want a fresh balance), not subject
        to the run budget."""
        url = f"{self._settings.dataforseo_base_url}/v3/appendix/user_data"
        response = httpx.get(
            url,
            auth=(self._settings.dataforseo_login, self._settings.dataforseo_password),
            timeout=self._settings.http_read_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        return (body.get("tasks") or [{}])[0]

    def _do_post(self, endpoint: str, payload: list[dict[str, Any]]) -> dict[str, Any]:
        url = f"{self._settings.dataforseo_base_url}{endpoint}"
        timeout = httpx.Timeout(
            connect=self._settings.http_connect_timeout_seconds,
            read=self._settings.http_read_timeout_seconds,
            write=self._settings.http_read_timeout_seconds,
            pool=self._settings.http_connect_timeout_seconds,
        )
        try:
            response = httpx.post(
                url,
                json=payload,
                auth=(self._settings.dataforseo_login, self._settings.dataforseo_password),
                timeout=timeout,
            )
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise RetryableError(f"transport error calling {endpoint}: {exc}") from exc

        if response.status_code in _RETRYABLE_HTTP_STATUS:
            raise RetryableError(
                f"HTTP {response.status_code} from {endpoint}",
                retry_after=_retry_after_seconds(response.headers),
            )
        if response.status_code >= 400:
            raise NonRetryableError(f"HTTP {response.status_code} from {endpoint}: {response.text[:300]}")

        body = response.json()
        self._record_cost(endpoint, body)
        task = (body.get("tasks") or [{}])[0]
        outcome = _classify_inner_status(task.get("status_code"))
        if outcome == "ok":
            return task
        message = f"DataForSEO status {task.get('status_code')}: {task.get('status_message')}"
        if outcome == "retryable":
            raise RetryableError(message)
        raise NonRetryableError(message)

    def _record_cost(self, endpoint: str, body: dict[str, Any]) -> None:
        cost = float(body.get("cost") or sum(float(t.get("cost") or 0) for t in body.get("tasks") or []))
        if self._budget is not None and cost:
            self._budget.record_actual_cost(endpoint, cost)
        if cost:
            dataforseo_cost_usd_total.labels(endpoint).inc(cost)

    def _get_cached(self, key: str) -> dict[str, Any] | None:
        row = get_session().get(ApiCache, key)
        if row is None:
            return None
        if row.expires_at < datetime.now(UTC):
            return None
        return row.response

    def _set_cached(self, key: str, endpoint: str, task: dict[str, Any]) -> None:
        session = get_session()
        expires_at = datetime.now(UTC) + timedelta(seconds=self._settings.api_cache_ttl_seconds)
        existing = session.get(ApiCache, key)
        if existing is not None:
            existing.response = task
            existing.expires_at = expires_at
        else:
            session.add(
                ApiCache(
                    key=key,
                    endpoint=endpoint,
                    response=task,
                    cost=float(task.get("cost") or 0),
                    expires_at=expires_at,
                )
            )
        session.commit()
