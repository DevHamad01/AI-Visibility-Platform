"""Shared resilience primitives used by every external call (DataForSEO, LLM
providers): error classification, retry with exponential backoff + full
jitter, and a per-dependency circuit breaker. CLAUDE.md sections 1 and 5.

Call sites never see raw transport exceptions — they raise `RetryableError`
(optionally carrying a `retry_after` from the server) or `NonRetryableError`,
and `call_with_retry` turns that into either a result or a typed failure,
plus metrics and structured logs for every attempt.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from tenacity import RetryCallState, Retrying, retry_if_exception_type, stop_after_attempt
from tenacity import wait_random_exponential as _wait_random_exponential

from app.core.logging import get_logger
from app.core.metrics import circuit_state, external_calls_total, external_retries_total

logger = get_logger(__name__)


class RetryableError(Exception):
    """Raised by call sites for errors worth retrying: timeouts, connection
    errors, 429 (optionally with Retry-After), 5xx, or a provider's own
    "try again later" status."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NonRetryableError(Exception):
    """Raised by call sites for errors that will never succeed on retry:
    4xx validation/auth/plan errors, malformed responses, etc."""


class CircuitOpenError(Exception):
    def __init__(self, dependency: str) -> None:
        super().__init__(f"Circuit breaker open for dependency '{dependency}' — failing fast.")
        self.dependency = dependency


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Closed -> Open after `failure_threshold` *consecutive* failures ->
    Half-open after `cooldown_seconds` (lets exactly one call through to
    test recovery) -> Closed on success or back to Open on failure."""

    def __init__(self, dependency: str, failure_threshold: int, cooldown_seconds: float) -> None:
        self.dependency = dependency
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at: float | None = None
        self._lock = threading.Lock()
        circuit_state.labels(dependency).set(0)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state is CircuitState.OPEN and self._opened_at is not None:
                if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def before_call(self) -> None:
        if self.state is CircuitState.OPEN:
            raise CircuitOpenError(self.dependency)

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._state = CircuitState.CLOSED
            self._opened_at = None
            circuit_state.labels(self.dependency).set(0)

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                circuit_state.labels(self.dependency).set(1)
                logger.warning(
                    "circuit_opened",
                    dependency=self.dependency,
                    consecutive_failures=self._consecutive_failures,
                )


_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_breakers_lock = threading.Lock()


def get_circuit_breaker(dependency: str, failure_threshold: int, cooldown_seconds: float) -> CircuitBreaker:
    with _circuit_breakers_lock:
        breaker = _circuit_breakers.get(dependency)
        if breaker is None:
            breaker = CircuitBreaker(dependency, failure_threshold, cooldown_seconds)
            _circuit_breakers[dependency] = breaker
        return breaker


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_base_seconds: float
    backoff_max_seconds: float


def call_with_retry[T](
    fn: Callable[[], T],
    *,
    dependency: str,
    endpoint: str,
    policy: RetryPolicy,
    circuit: CircuitBreaker,
) -> T:
    """Runs `fn()`, retrying on `RetryableError` with exponential backoff and
    full jitter (or the server-provided `retry_after` when present), behind a
    circuit breaker. Raises `CircuitOpenError`, the last `RetryableError`, or
    a `NonRetryableError` on failure. Logs and records metrics either way."""

    circuit.before_call()

    def _wait(retry_state: RetryCallState) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if isinstance(exc, RetryableError) and exc.retry_after is not None:
            return exc.retry_after
        return _wait_random_exponential(
            multiplier=policy.backoff_base_seconds, max=policy.backoff_max_seconds
        )(retry_state)

    retryer = Retrying(
        stop=stop_after_attempt(policy.max_attempts),
        wait=_wait,
        retry=retry_if_exception_type(RetryableError),
        reraise=True,
    )

    try:
        result: T | None = None
        for attempt in retryer:
            with attempt:
                result = fn()
        attempts = retryer.statistics.get("attempt_number", 1)
        if attempts > 1:
            external_retries_total.labels(dependency, endpoint).inc(attempts - 1)
        circuit.record_success()
        external_calls_total.labels(dependency, endpoint, "success").inc()
        logger.info(
            "external_call_succeeded", dependency=dependency, endpoint=endpoint, attempts=attempts
        )
        assert result is not None
        return result
    except RetryableError:
        attempts = retryer.statistics.get("attempt_number", 1)
        if attempts > 1:
            external_retries_total.labels(dependency, endpoint).inc(attempts - 1)
        circuit.record_failure()
        external_calls_total.labels(dependency, endpoint, "retryable_exhausted").inc()
        logger.warning(
            "external_call_exhausted_retries", dependency=dependency, endpoint=endpoint, attempts=attempts
        )
        raise
    except NonRetryableError:
        circuit.record_failure()
        external_calls_total.labels(dependency, endpoint, "non_retryable").inc()
        logger.warning("external_call_non_retryable", dependency=dependency, endpoint=endpoint)
        raise
