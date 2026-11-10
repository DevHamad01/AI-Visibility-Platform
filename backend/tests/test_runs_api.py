"""Runs API status codes (CLAUDE.md section 3): 202 + Location on create,
409 when a run is already queued/running for the brand, 404 for a brand or
run that doesn't exist. The RQ job is enqueued for real (into the test
Redis) but never consumed — no worker runs in this test, which is exactly
what we want: the run stays `queued`, perfect for triggering the 409.
"""

from __future__ import annotations

import uuid

from flask.testing import FlaskClient

PROBLEM_CONTENT_TYPE = "application/problem+json"


def _create_brand(client: FlaskClient) -> str:
    response = client.post("/api/v1/brands", json={"name": "Acme Corp", "domain": "acme.com"})
    assert response.status_code == 201
    return response.get_json()["id"]


def test_create_run_returns_202_with_location(client: FlaskClient) -> None:
    brand_id = _create_brand(client)

    response = client.post(f"/api/v1/brands/{brand_id}/runs")

    assert response.status_code == 202
    body = response.get_json()
    assert body["status"] == "queued"
    assert response.headers["Location"] == f"/api/v1/runs/{body['id']}"


def test_second_run_while_one_active_returns_409(client: FlaskClient) -> None:
    brand_id = _create_brand(client)
    first = client.post(f"/api/v1/brands/{brand_id}/runs")
    assert first.status_code == 202

    second = client.post(f"/api/v1/brands/{brand_id}/runs")

    assert second.status_code == 409
    assert second.content_type == PROBLEM_CONTENT_TYPE


def test_same_idempotency_key_returns_same_run(client: FlaskClient) -> None:
    brand_id = _create_brand(client)
    headers = {"Idempotency-Key": "test-key-123"}

    first = client.post(f"/api/v1/brands/{brand_id}/runs", headers=headers)
    second = client.post(f"/api/v1/brands/{brand_id}/runs", headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.get_json()["id"] == second.get_json()["id"]


def test_create_run_for_missing_brand_returns_404(client: FlaskClient) -> None:
    response = client.post(f"/api/v1/brands/{uuid.uuid4()}/runs")
    assert response.status_code == 404
    assert response.content_type == PROBLEM_CONTENT_TYPE


def test_get_missing_run_returns_404(client: FlaskClient) -> None:
    response = client.get(f"/api/v1/runs/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.content_type == PROBLEM_CONTENT_TYPE


def test_get_run_includes_stages_trace(client: FlaskClient) -> None:
    brand_id = _create_brand(client)
    created = client.post(f"/api/v1/brands/{brand_id}/runs").get_json()

    response = client.get(f"/api/v1/runs/{created['id']}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "queued"
    assert body["brand_id"] == brand_id


def test_list_brand_runs(client: FlaskClient) -> None:
    brand_id = _create_brand(client)
    client.post(f"/api/v1/brands/{brand_id}/runs")

    response = client.get(f"/api/v1/brands/{brand_id}/runs")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body["items"]) == 1
    assert "stages" not in body["items"][0]


def test_overview_returns_brand_list(client: FlaskClient) -> None:
    brand_id = _create_brand(client)
    client.post(f"/api/v1/brands/{brand_id}/runs")

    response = client.get("/api/v1/overview")

    assert response.status_code == 200
    body = response.get_json()
    assert len(body["brands"]) == 1
    assert body["brands"][0]["latest_run_status"] == "queued"
