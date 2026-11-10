"""Test fixtures.

Tests run inside the `api` container against a real, throwaway Postgres
database (`<db>_test`) on the same Postgres server — not SQLite. Our models
use Postgres-native JSONB/UUID column types, so SQLite would silently behave
differently (or not support them at all); a real Postgres database is the
only thing that actually exercises the schema we ship.

The test database is dropped and recreated once per test session; rows are
truncated between individual tests for isolation.
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.engine import make_url

from app import create_app
from app.core.config import Settings, get_settings
from app.core.resilience import _circuit_breakers
from app.db.base import Base, get_engine, remove_session


def _test_database_url() -> str:
    url = make_url(get_settings().database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


def _admin_database_url() -> str:
    url = make_url(get_settings().database_url)
    admin_url = url.set(database="postgres").render_as_string(hide_password=False)
    return admin_url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture(scope="session", autouse=True)
def _create_test_database() -> Iterator[None]:
    test_db_name = make_url(_test_database_url()).database
    with psycopg.connect(_admin_database_url(), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{test_db_name}"')
        conn.execute(f'CREATE DATABASE "{test_db_name}"')
    yield


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    base = get_settings()
    test_redis_url = base.redis_url.rsplit("/", 1)[0] + "/15"
    return base.model_copy(
        update={
            "database_url": _test_database_url(),
            "redis_url": test_redis_url,
            "sentry_dsn": "",
        }
    )


@pytest.fixture()
def app(test_settings: Settings) -> Iterator[Flask]:
    flask_app = create_app(test_settings)
    Base.metadata.create_all(get_engine())
    yield flask_app
    with get_engine().begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    remove_session()
    get_engine().dispose()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture(autouse=True)
def _reset_circuit_breakers() -> Iterator[None]:
    """Circuit breakers live in a process-global registry keyed by dependency
    name, so a circuit opened by one test would otherwise leak into the next."""
    _circuit_breakers.clear()
    yield
    _circuit_breakers.clear()


@pytest.fixture()
def resilient_settings(test_settings: Settings) -> Settings:
    """Fast retry/circuit-breaker settings so resilience tests don't sleep
    through real exponential backoff."""
    return test_settings.model_copy(
        update={
            "retry_max_attempts": 3,
            "retry_backoff_base_seconds": 0.001,
            "retry_backoff_max_seconds": 0.01,
            "circuit_breaker_failure_threshold": 3,
            "circuit_breaker_cooldown_seconds": 0.05,
            "dataforseo_login": "test-login",
            "dataforseo_password": "test-password",
            "groq_api_key": "test-groq-key",
            "gemini_api_key": "test-gemini-key",
            "llm_chain": "groq:test-model-a,gemini:test-model-b",
        }
    )
