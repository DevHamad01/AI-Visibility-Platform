"""DataForSEOClient resilience behavior: retry/backoff, Retry-After, no
retry on non-retryable errors, circuit breaker, and the response cache.
All HTTP is mocked with respx — no real network."""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from app.core.resilience import CircuitOpenError, NonRetryableError, RetryableError
from app.tools.dataforseo.budget import BudgetExceededError, RunBudget
from app.tools.dataforseo.client import DataForSEOClient

ENDPOINT = "/v3/serp/google/organic/live/advanced"


def _ok_body(cost: float = 0.001) -> dict:
    return {
        "status_code": 20000,
        "status_message": "Ok.",
        "cost": cost,
        "tasks": [
            {
                "status_code": 20000,
                "status_message": "Ok.",
                "cost": cost,
                "result": [{"items": []}],
            }
        ],
    }


@pytest.mark.usefixtures("app")
@respx.mock
def test_retry_then_success_on_503(resilient_settings):
    url = f"{resilient_settings.dataforseo_base_url}{ENDPOINT}"
    route = respx.post(url).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=_ok_body())]
    )
    client = DataForSEOClient(resilient_settings)

    task = client.post(ENDPOINT, [{"keyword": "x"}])

    assert task["status_code"] == 20000
    assert route.call_count == 2


@pytest.mark.usefixtures("app")
@respx.mock
def test_429_honours_retry_after(resilient_settings):
    url = f"{resilient_settings.dataforseo_base_url}{ENDPOINT}"
    respx.post(url).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=_ok_body()),
        ]
    )
    client = DataForSEOClient(resilient_settings)

    start = time.monotonic()
    task = client.post(ENDPOINT, [{"keyword": "x"}])
    elapsed = time.monotonic() - start

    assert task["status_code"] == 20000
    # Retry-After: 0 means an immediate retry, not the (much larger) default
    # exponential backoff ceiling — proves the header was actually honoured.
    assert elapsed < 1.0


@pytest.mark.usefixtures("app")
@respx.mock
def test_no_retry_on_401(resilient_settings):
    url = f"{resilient_settings.dataforseo_base_url}{ENDPOINT}"
    route = respx.post(url).mock(return_value=httpx.Response(401, text="unauthorized"))
    client = DataForSEOClient(resilient_settings)

    with pytest.raises(NonRetryableError):
        client.post(ENDPOINT, [{"keyword": "x"}])

    assert route.call_count == 1


@pytest.mark.usefixtures("app")
@respx.mock
def test_no_retry_on_account_not_verified(resilient_settings):
    """Real response captured from a live call against an unverified
    DataForSEO trial account: HTTP 403, inner status_code 40104, cost 0,
    tasks: null. Must be classified non-retryable (it is an account-state
    error, not a transient one) and must never charge the run budget."""
    url = f"{resilient_settings.dataforseo_base_url}{ENDPOINT}"
    route = respx.post(url).mock(
        return_value=httpx.Response(
            403,
            json={
                "version": "0.1.20261103",
                "status_code": 40104,
                "status_message": (
                    "Please verify your account before using the API. "
                    "You can complete verification in the user panel: https://app.dataforseo.com/."
                ),
                "time": "0 sec.",
                "cost": 0,
                "tasks_count": 0,
                "tasks_error": 0,
                "tasks": None,
            },
        )
    )
    client = DataForSEOClient(resilient_settings)

    with pytest.raises(NonRetryableError, match="40104"):
        client.post(ENDPOINT, [{"keyword": "x"}])

    assert route.call_count == 1


@pytest.mark.usefixtures("app")
@respx.mock
def test_circuit_opens_after_n_failures_and_fails_fast(resilient_settings):
    url = f"{resilient_settings.dataforseo_base_url}{ENDPOINT}"
    route = respx.post(url).mock(return_value=httpx.Response(503))
    client = DataForSEOClient(resilient_settings)

    for _ in range(resilient_settings.circuit_breaker_failure_threshold):
        with pytest.raises(RetryableError):
            client.post(ENDPOINT, [{"keyword": "x"}])

    calls_before_open = route.call_count
    with pytest.raises(CircuitOpenError):
        client.post(ENDPOINT, [{"keyword": "x"}])

    assert route.call_count == calls_before_open  # failed fast — no new HTTP call


@pytest.mark.usefixtures("app")
@respx.mock
def test_cache_hit_avoids_second_http_call(resilient_settings):
    url = f"{resilient_settings.dataforseo_base_url}{ENDPOINT}"
    route = respx.post(url).mock(return_value=httpx.Response(200, json=_ok_body(cost=0.002)))
    client = DataForSEOClient(resilient_settings)
    payload = [{"keyword": "same-query"}]

    first = client.post(ENDPOINT, payload)
    second = client.post(ENDPOINT, payload)

    assert first == second
    assert route.call_count == 1


@pytest.mark.usefixtures("app")
@respx.mock
def test_budget_exceeded_never_calls_http(resilient_settings):
    url = f"{resilient_settings.dataforseo_base_url}{ENDPOINT}"
    route = respx.post(url).mock(return_value=httpx.Response(200, json=_ok_body()))
    budget = RunBudget(max_cost_usd=0.01)
    client = DataForSEOClient(resilient_settings, budget=budget)

    with pytest.raises(BudgetExceededError):
        client.post(ENDPOINT, [{"keyword": "x"}], estimated_cost=0.02)

    assert not route.called
    assert budget.spent_usd == 0.0


@pytest.mark.usefixtures("app")
@respx.mock
def test_cache_hit_bypasses_budget_check(resilient_settings):
    url = f"{resilient_settings.dataforseo_base_url}{ENDPOINT}"
    respx.post(url).mock(return_value=httpx.Response(200, json=_ok_body(cost=0.005)))
    budget = RunBudget(max_cost_usd=0.10)
    client = DataForSEOClient(resilient_settings, budget=budget)
    payload = [{"keyword": "same-query"}]

    client.post(ENDPOINT, payload, estimated_cost=0.005)
    assert budget.spent_usd == 0.005

    # Second call is a cache hit — free, so it must not be blocked even if
    # the (irrelevant, since cached) estimated_cost would otherwise exceed
    # what's left of the budget.
    client.post(ENDPOINT, payload, estimated_cost=1.0)
    assert budget.spent_usd == 0.005
