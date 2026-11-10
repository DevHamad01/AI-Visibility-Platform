"""Brand CRUD: create (201 + Location), validation (422 problem), missing (404 problem)."""

from __future__ import annotations

import uuid

from flask.testing import FlaskClient

PROBLEM_CONTENT_TYPE = "application/problem+json"


def test_create_brand_returns_201_with_location(client: FlaskClient) -> None:
    response = client.post("/api/v1/brands", json={"name": "Acme", "domain": "acme.com"})

    assert response.status_code == 201
    body = response.get_json()
    assert body["name"] == "Acme"
    assert body["domain"] == "acme.com"
    assert response.headers["Location"] == f"/api/v1/brands/{body['id']}"


def test_create_brand_with_invalid_domain_returns_422_problem(client: FlaskClient) -> None:
    response = client.post("/api/v1/brands", json={"name": "Acme", "domain": "not a domain"})

    assert response.status_code == 422
    assert response.content_type == PROBLEM_CONTENT_TYPE
    body = response.get_json()
    assert body["status"] == 422
    assert body["title"] == "Validation Error"
    assert body["errors"]
    assert body["trace_id"]


def test_get_missing_brand_returns_404_problem(client: FlaskClient) -> None:
    response = client.get(f"/api/v1/brands/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.content_type == PROBLEM_CONTENT_TYPE
    body = response.get_json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["trace_id"]


def test_update_and_delete_brand(client: FlaskClient) -> None:
    created = client.post("/api/v1/brands", json={"name": "Acme", "domain": "acme.com"}).get_json()

    patched = client.patch(f"/api/v1/brands/{created['id']}", json={"name": "Acme Corp"})
    assert patched.status_code == 200
    assert patched.get_json()["name"] == "Acme Corp"

    deleted = client.delete(f"/api/v1/brands/{created['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/brands/{created['id']}")
    assert missing.status_code == 404


def test_list_brands_pagination_envelope(client: FlaskClient) -> None:
    client.post("/api/v1/brands", json={"name": "Acme", "domain": "acme.com"})

    response = client.get("/api/v1/brands?limit=1")
    assert response.status_code == 200
    body = response.get_json()
    assert "items" in body
    assert "next_cursor" in body
