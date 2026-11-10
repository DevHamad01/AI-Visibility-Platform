"""LLMClient — the one interface every pipeline agent uses:
`complete_structured(prompt, schema)` and `call_tools(prompt, tools)`.
Agents never import a provider SDK (CLAUDE.md section 1).

Neither method relies on provider-native structured-output/strict modes:
`complete_structured` asks for JSON in the prompt, parses it, validates with
Pydantic, and does exactly one repair retry (re-asking with the validation
error attached) before giving up on that provider and falling through to the
next one in the chain. `call_tools` validates whatever tool calls the
provider returns against each tool's own args model and drops (logs, never
executes) any call with unknown name or invalid/partial arguments.
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.metrics import llm_fallbacks_total
from app.core.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    NonRetryableError,
    RetryableError,
    RetryPolicy,
    call_with_retry,
    get_circuit_breaker,
)
from app.llm.chain import ChainEntry, build_active_chain
from app.llm.errors import LLMAllProvidersFailedError, LLMOutputError
from app.llm.providers import call_provider
from app.llm.types import StructuredResult, ToolCall, ToolCallsResult, ToolSpec

logger = get_logger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

_API_KEY_FIELD = {
    "groq": "groq_api_key",
    "gemini": "gemini_api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
}

_FALLTHROUGH_EXCEPTIONS = (RetryableError, NonRetryableError, CircuitOpenError, LLMOutputError)


def _extract_json(text: str) -> str:
    """Providers sometimes wrap JSON in a ```json fence or add a stray
    sentence around it. Grab the outermost {...} or [...] block."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return text
    start = min(starts)
    ends = [i for i in (text.rfind("}"), text.rfind("]")) if i != -1]
    end = max(ends) if ends else len(text) - 1
    return text[start : end + 1]


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._chain = build_active_chain(settings)
        self._policy = RetryPolicy(
            max_attempts=settings.retry_max_attempts,
            backoff_base_seconds=settings.retry_backoff_base_seconds,
            backoff_max_seconds=settings.retry_backoff_max_seconds,
        )

    @property
    def chain(self) -> list[ChainEntry]:
        return self._chain

    def _api_key(self, provider: str) -> str:
        return getattr(self._settings, _API_KEY_FIELD[provider])

    def _circuit(self, provider: str) -> CircuitBreaker:
        return get_circuit_breaker(
            f"llm:{provider}",
            self._settings.circuit_breaker_failure_threshold,
            self._settings.circuit_breaker_cooldown_seconds,
        )

    def _record_fallback(self, index: int, exc: Exception) -> None:
        if index + 1 >= len(self._chain):
            return
        from_entry, to_entry = self._chain[index], self._chain[index + 1]
        llm_fallbacks_total.labels(from_entry.provider, to_entry.provider).inc()
        logger.warning(
            "llm_fallback",
            from_provider=from_entry.provider,
            to_provider=to_entry.provider,
            reason=type(exc).__name__,
        )

    def complete_structured(
        self, prompt: str, schema: type[SchemaT], *, system: str | None = None
    ) -> StructuredResult:
        if not self._chain:
            raise LLMAllProvidersFailedError(["<no providers configured>"])

        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_system = (
            f"{system or 'You are a precise assistant.'}\n\n"
            "Respond with ONLY a single JSON object matching this JSON schema. "
            "No prose, no markdown fences, no explanation.\n\n"
            f"{schema_json}"
        )

        failures: list[str] = []
        for index, entry in enumerate(self._chain):
            try:
                value, attempts = self._complete_structured_with_provider(
                    entry, full_system, prompt, schema
                )
                return StructuredResult(
                    value=value, provider=entry.provider, model=entry.model, attempts=attempts
                )
            except _FALLTHROUGH_EXCEPTIONS as exc:
                failures.append(f"{entry.provider}:{entry.model} ({type(exc).__name__})")
                self._record_fallback(index, exc)
                continue
        raise LLMAllProvidersFailedError(failures)

    def _complete_structured_with_provider(
        self, entry: ChainEntry, system: str, user_prompt: str, schema: type[SchemaT]
    ) -> tuple[SchemaT, int]:
        api_key = self._api_key(entry.provider)
        circuit = self._circuit(entry.provider)
        attempt_count = 0

        def _raw_call(text: str) -> str:
            nonlocal attempt_count
            attempt_count += 1
            completion = call_provider(
                entry,
                api_key=api_key,
                system=system,
                user=text,
                tools=None,
                timeout=self._settings.llm_read_timeout_seconds,
            )
            if not completion.text:
                raise NonRetryableError(f"{entry.provider}:{entry.model} returned no text content.")
            return completion.text

        def _do() -> SchemaT:
            raw = _raw_call(user_prompt)
            try:
                return schema.model_validate_json(_extract_json(raw))
            except ValidationError as exc:
                repair_prompt = (
                    f"{user_prompt}\n\nYour previous response was invalid: {exc}\n"
                    "Return corrected JSON only, matching the schema exactly."
                )
                raw2 = _raw_call(repair_prompt)
                try:
                    return schema.model_validate_json(_extract_json(raw2))
                except ValidationError as exc2:
                    raise LLMOutputError(entry.provider, entry.model, str(exc2)) from exc2

        value = call_with_retry(
            _do,
            dependency=f"llm:{entry.provider}",
            endpoint=entry.model,
            policy=self._policy,
            circuit=circuit,
        )
        return value, attempt_count

    def call_tools(
        self, prompt: str, tools: list[ToolSpec], *, system: str | None = None
    ) -> ToolCallsResult:
        if not self._chain:
            raise LLMAllProvidersFailedError(["<no providers configured>"])

        full_system = system or "You are a precise assistant. Use the available tools when appropriate."

        failures: list[str] = []
        for index, entry in enumerate(self._chain):
            api_key = self._api_key(entry.provider)
            circuit = self._circuit(entry.provider)

            def _call(entry: ChainEntry = entry, api_key: str = api_key) -> list[dict]:
                completion = call_provider(
                    entry,
                    api_key=api_key,
                    system=full_system,
                    user=prompt,
                    tools=tools,
                    timeout=self._settings.llm_read_timeout_seconds,
                )
                return completion.tool_calls

            try:
                raw_calls = call_with_retry(
                    _call,
                    dependency=f"llm:{entry.provider}",
                    endpoint=entry.model,
                    policy=self._policy,
                    circuit=circuit,
                )
            except (RetryableError, NonRetryableError, CircuitOpenError) as exc:
                failures.append(f"{entry.provider}:{entry.model} ({type(exc).__name__})")
                self._record_fallback(index, exc)
                continue

            validated = self._validate_tool_calls(raw_calls, tools)
            return ToolCallsResult(calls=validated, provider=entry.provider, model=entry.model)
        raise LLMAllProvidersFailedError(failures)

    @staticmethod
    def _validate_tool_calls(raw_calls: list[dict], tools: list[ToolSpec]) -> list[ToolCall]:
        specs_by_name = {t.name: t for t in tools}
        validated: list[ToolCall] = []
        for raw in raw_calls:
            name = raw.get("name")
            spec = specs_by_name.get(name)
            if spec is None:
                logger.warning("tool_call_unknown_tool", tool=name)
                continue
            try:
                parsed = spec.args_model.model_validate(raw.get("arguments") or {})
            except ValidationError as exc:
                logger.warning("tool_call_invalid_arguments", tool=name, errors=exc.errors())
                continue
            validated.append(ToolCall(name=name, arguments=parsed.model_dump()))
        return validated
