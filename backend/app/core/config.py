"""Application settings, loaded from environment variables (see root .env.example).

Settings that the app cannot run without (database, redis, secret key) have no
default: pydantic-settings raises a ValidationError if they are missing, and
`get_settings()` turns that into a single clear, fail-fast message instead of
a stack trace. Settings only needed by later phases (DataForSEO, LLM keys)
default to empty so Phase 1 can boot without them.
"""

from __future__ import annotations

import sys
from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- Required to boot ---
    database_url: str
    redis_url: str
    secret_key: str

    # --- App ---
    flask_env: str = "production"
    log_level: str = "INFO"
    sentry_dsn: str = ""

    # --- Cache / pipeline budgets (used from Phase 2 onward) ---
    api_cache_ttl_seconds: int = 86400
    max_queries_per_run: int = 12
    max_serp_calls_per_run: int = 12
    run_timeout_seconds: int = 600
    demo_fail_serp: bool = False  # One-off failure exercise only; never enabled by default.

    # --- HTTP timeouts (used from Phase 2 onward) ---
    http_connect_timeout_seconds: float = 5
    http_read_timeout_seconds: float = 60
    llm_read_timeout_seconds: float = 60

    # --- Retry / circuit breaker (used from Phase 2 onward) ---
    retry_max_attempts: int = 4
    retry_backoff_base_seconds: float = 0.5
    retry_backoff_max_seconds: float = 20
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_seconds: int = 30

    # --- DataForSEO (used from Phase 2 onward) ---
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    dataforseo_base_url: str = "https://api.dataforseo.com"
    # Hard cap on estimated + actual DataForSEO spend per pipeline run. A
    # trial/sandbox account's balance is tiny and must survive the whole
    # project, not just one run.
    dataforseo_max_cost_per_run: float = 0.15

    # --- LLM chain (used from Phase 2 onward) ---
    llm_chain: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing_or_invalid = ", ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])} ({err['msg']})" for err in exc.errors()
        )
        print(
            f"FATAL: invalid configuration — {missing_or_invalid}. "
            "Check your .env against .env.example.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
