"""Shared value types for the LLM layer. Agents (and DataForSEO tool modules,
for tool-calling) import `ToolSpec`; nothing here talks to a provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class ToolSpec:
    """A tool exposed to the LLM for tool-calling. `args_model` is both the
    source of the JSON schema sent to the provider and the validator used
    on whatever arguments the LLM returns."""

    name: str
    description: str
    args_model: type[BaseModel]

    def to_openai_function(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class StructuredResult:
    value: BaseModel
    provider: str
    model: str
    attempts: int


@dataclass(frozen=True)
class ToolCallsResult:
    calls: list[ToolCall]
    provider: str
    model: str
