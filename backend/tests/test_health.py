"""Liveness/readiness probes."""

from __future__ import annotations

from flask.testing import FlaskClient


def test_healthz_ok(client: FlaskClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_readyz_checks_dependencies(client: FlaskClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.get_json()
    assert body["checks"]["database"] == "ok"
