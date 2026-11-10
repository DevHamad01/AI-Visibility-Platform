"""Talks to exactly one provider per call: builds the request, classifies
its errors into `RetryableError` / `NonRetryableError`, and returns a
provider-agnostic `RawCompletion`. No JSON parsing, validation or retry
policy lives here — that's `app.llm.client`.

openai, groq and gemini all go through the `openai` SDK (groq/gemini via
their OpenAI-compatible base URLs — CLAUDE.md section 1). anthropic uses its
own SDK. Error classification is based on each SDK's actual exception
hierarchy (openai: APIConnectionError/APITimeoutError/RateLimitError/
InternalServerError/APIStatusError; anthropic mirrors the same shape).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import anthropic
import openai as openai_sdk

from app.core.resilience import NonRetryableError, RetryableError
from app.llm.chain import ChainEntry
from app.llm.types import ToolSpec

_OPENAI_COMPAT_BASE_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    # "openai": SDK default (api.openai.com) — no override needed.
}

_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class RawCompletion:
    text: str | None
    tool_calls: list[dict[str, Any]]


def _retry_after_seconds(headers: Mapping[str, str] | None) -> float | None:
    if not headers:
        return None
    value = headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _classify_openai_exception(exc: Exception) -> Exception:
    if isinstance(exc, openai_sdk.APIConnectionError | openai_sdk.APITimeoutError):
        return RetryableError(str(exc))
    if isinstance(exc, openai_sdk.RateLimitError):
        headers = getattr(exc.response, "headers", None) if exc.response is not None else None
        return RetryableError(str(exc), retry_after=_retry_after_seconds(headers))
    if isinstance(exc, openai_sdk.APIStatusError):
        if exc.status_code in _RETRYABLE_HTTP_STATUS:
            return RetryableError(str(exc))
        return NonRetryableError(str(exc))
    return NonRetryableError(str(exc))


def _classify_anthropic_exception(exc: Exception) -> Exception:
    if isinstance(exc, anthropic.APIConnectionError | anthropic.APITimeoutError):
        return RetryableError(str(exc))
    if isinstance(exc, anthropic.RateLimitError):
        headers = getattr(exc.response, "headers", None) if exc.response is not None else None
        return RetryableError(str(exc), retry_after=_retry_after_seconds(headers))
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code in _RETRYABLE_HTTP_STATUS:
            return RetryableError(str(exc))
        return NonRetryableError(str(exc))
    return NonRetryableError(str(exc))


def _call_openai_compatible(
    *,
    provider: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    tools: list[ToolSpec] | None,
    timeout: float,
) -> RawCompletion:
    # max_retries=0: our own call_with_retry (app.core.resilience) is the one
    # retry/backoff/circuit-breaker policy — the SDK's built-in retries would
    # silently double up on top of it.
    client = openai_sdk.OpenAI(
        api_key=api_key,
        base_url=_OPENAI_COMPAT_BASE_URLS.get(provider),
        timeout=timeout,
        max_retries=0,
    )
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if tools:
        kwargs["tools"] = [t.to_openai_function() for t in tools]
        kwargs["tool_choice"] = "auto"

    try:
        response = client.chat.completions.create(**kwargs)
    except (openai_sdk.APIConnectionError, openai_sdk.APITimeoutError, openai_sdk.APIStatusError) as exc:
        raise _classify_openai_exception(exc) from exc

    choice = response.choices[0]
    tool_calls: list[dict[str, Any]] = []
    for call in choice.message.tool_calls or []:
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        tool_calls.append({"name": call.function.name, "arguments": arguments})
    return RawCompletion(text=choice.message.content, tool_calls=tool_calls)


def _call_anthropic(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    tools: list[ToolSpec] | None,
    timeout: float,
) -> RawCompletion:
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if tools:
        kwargs["tools"] = [
            {"name": t.name, "description": t.description, "input_schema": t.args_model.model_json_schema()}
            for t in tools
        ]

    try:
        response = client.messages.create(**kwargs)
    except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.APIStatusError) as exc:
        raise _classify_anthropic_exception(exc) from exc

    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append({"name": block.name, "arguments": block.input})
    return RawCompletion(text="\n".join(text_parts) if text_parts else None, tool_calls=tool_calls)


def call_provider(
    entry: ChainEntry,
    *,
    api_key: str,
    system: str,
    user: str,
    tools: list[ToolSpec] | None,
    timeout: float,
) -> RawCompletion:
    if entry.provider in ("openai", "groq", "gemini"):
        return _call_openai_compatible(
            provider=entry.provider,
            api_key=api_key,
            model=entry.model,
            system=system,
            user=user,
            tools=tools,
            timeout=timeout,
        )
    if entry.provider == "anthropic":
        return _call_anthropic(
            api_key=api_key, model=entry.model, system=system, user=user, tools=tools, timeout=timeout
        )
    raise NonRetryableError(f"Unknown LLM provider '{entry.provider}'.")
