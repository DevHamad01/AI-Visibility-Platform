"""Budget and cache boundaries tested independently of Postgres storage."""

import httpx
import pytest
import respx

from app.core.resilience import NonRetryableError, RetryableError
from app.tools.dataforseo.budget import RunBudget
from app.tools.dataforseo.client import DataForSEOClient

ENDPOINT = "/v3/serp/google/organic/live/advanced"


def uncached_client(settings, monkeypatch, budget):
    client = DataForSEOClient(settings, budget)
    monkeypatch.setattr(client, "_get_cached", lambda _key: None)
    monkeypatch.setattr(client, "_set_cached", lambda *_args: None)
    return client


@respx.mock
def test_charged_failed_attempts_are_counted_before_retry(resilient_settings, monkeypatch):
    budget = RunBudget(0.15)
    client = uncached_client(resilient_settings, monkeypatch, budget)
    route = respx.post(f"{resilient_settings.dataforseo_base_url}{ENDPOINT}").mock(
        return_value=httpx.Response(
            200,
            json={"cost": 0.01, "tasks": [{"status_code": 50000, "status_message": "Error", "cost": 0.01}]},
        )
    )
    with pytest.raises(RetryableError):
        client.post(ENDPOINT, [{}], estimated_cost=0.01)
    assert route.call_count == resilient_settings.retry_max_attempts
    assert budget.spent_usd == pytest.approx(0.01 * route.call_count)
    assert budget.remaining() == pytest.approx(0.15 - budget.spent_usd)


@respx.mock
def test_billed_nonretryable_task_is_not_free(resilient_settings, monkeypatch):
    budget = RunBudget(0.15)
    client = uncached_client(resilient_settings, monkeypatch, budget)
    respx.post(f"{resilient_settings.dataforseo_base_url}{ENDPOINT}").respond(
        200,
        json={"cost": 0.02, "tasks": [{"status_code": 40000, "status_message": "Task failed", "cost": 0.02}]},
    )
    with pytest.raises(NonRetryableError):
        client.post(ENDPOINT, [{}], estimated_cost=0.02)
    assert budget.spent_usd == pytest.approx(0.02)


def test_live_and_sandbox_caches_are_separate(resilient_settings, monkeypatch):
    keys = []
    for base in ["https://api.dataforseo.com", "https://sandbox.dataforseo.com"]:
        client = DataForSEOClient(resilient_settings.model_copy(update={"dataforseo_base_url": base}))
        monkeypatch.setattr(client, "_get_cached", lambda key: keys.append(key) or {"cached": True})
        assert client.post(ENDPOINT, [{}]) == {"cached": True}
    assert len(set(keys)) == 2
