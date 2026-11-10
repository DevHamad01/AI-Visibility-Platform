"""Run endpoints are stubbed in Phase 1 and return a 501 problem response."""

from __future__ import annotations

from flask.testing import FlaskClient


def test_create_run_returns_501_problem(client: FlaskClient) -> None:
    brand = client.post("/api/v1/brands", json={"name": "Acme", "domain": "acme.com"}).get_json()

    response = client.post(f"/api/v1/brands/{brand['id']}/runs")

    assert response.status_code == 501
    assert response.content_type == "application/problem+json"
    assert response.get_json()["status"] == 501
