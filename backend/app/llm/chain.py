"""Parses LLM_CHAIN (e.g. "groq:openai/gpt-oss-120b,gemini:gemini-3.5-flash-lite")
into an ordered list of providers to try. Provider choice and order live
entirely in config — agents never import a provider SDK directly."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_API_KEY_FIELD = {
    "groq": "groq_api_key",
    "gemini": "gemini_api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
}


@dataclass(frozen=True)
class ChainEntry:
    provider: str
    model: str


def parse_llm_chain(raw: str) -> list[ChainEntry]:
    entries: list[ChainEntry] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        provider, _, model = part.partition(":")
        provider = provider.strip().lower()
        model = model.strip()
        if not provider or not model:
            logger.warning("llm_chain_entry_malformed", entry=part)
            continue
        entries.append(ChainEntry(provider, model))
    return entries


def build_active_chain(settings: Settings) -> list[ChainEntry]:
    """Drops any entry whose provider has no API key configured, so (for
    example) an empty GEMINI_API_KEY still leaves a working chain of the
    remaining providers instead of failing on every call."""
    active: list[ChainEntry] = []
    for entry in parse_llm_chain(settings.llm_chain):
        field = _API_KEY_FIELD.get(entry.provider)
        if field is None:
            logger.warning("llm_provider_unknown", provider=entry.provider)
            continue
        if not getattr(settings, field):
            logger.warning("llm_provider_skipped_no_api_key", provider=entry.provider)
            continue
        active.append(entry)
    return active
