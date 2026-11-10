"""LLM-layer failure types. Transport/HTTP failures reuse
`app.core.resilience.RetryableError` / `NonRetryableError` — these two are
specific to the LLM layer's own contract."""

from __future__ import annotations


class LLMOutputError(Exception):
    """The provider responded, but its output never became valid JSON
    matching the requested schema, even after one repair retry."""

    def __init__(self, provider: str, model: str, detail: str) -> None:
        super().__init__(f"{provider}:{model} — {detail}")
        self.provider = provider
        self.model = model
        self.detail = detail


class LLMAllProvidersFailedError(Exception):
    """Every provider in the active chain failed (or the chain was empty)."""

    def __init__(self, attempts: list[str]) -> None:
        super().__init__(f"All LLM providers failed: {', '.join(attempts) or '<none configured>'}")
        self.attempts = attempts
