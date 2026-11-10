"""Minimal fixed-window rate limiter backed by Redis — used by
POST /client-errors (CLAUDE.md section 3: "rate-limited, size-limited")."""

from __future__ import annotations

from redis import Redis


def is_rate_limited(redis_client: Redis, key: str, *, limit: int, window_seconds: int) -> bool:
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, window_seconds)
    return count > limit
