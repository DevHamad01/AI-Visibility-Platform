"""LLMClient: JSON repair retry, typed failure on persistently-junk output,
provider fallback within the chain, and tool-call argument validation.
All HTTP mocked with respx — no real network, no real API keys needed."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from app.llm.chain import build_active_chain
from app.llm.client import LLMClient
from app.llm.errors import LLMOutputError
from app.llm.types import ToolSpec

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


class Greeting(BaseModel):
    message: str


class DummyToolArgs(BaseModel):
    keyword: str


DUMMY_TOOL = ToolSpec(name="dummy_tool", description="test tool", args_model=DummyToolArgs)


def _chat_response(content: str | None = None, tool_calls: list[dict] | None = None) -> dict:
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
            }
            for i, tc in enumerate(tool_calls)
        ]
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "test-model",
        "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
    }


@respx.mock
def test_complete_structured_repairs_once_then_succeeds(resilient_settings):
    respx.post(GROQ_URL).mock(
        side_effect=[
            httpx.Response(200, json=_chat_response(content="not json at all, sorry!")),
            httpx.Response(200, json=_chat_response(content=json.dumps({"message": "hello"}))),
        ]
    )
    client = LLMClient(resilient_settings)

    result = client.complete_structured("say hi", Greeting)

    assert result.value.message == "hello"
    assert result.provider == "groq"


@respx.mock
def test_junk_twice_raises_llm_output_error(resilient_settings):
    respx.post(GROQ_URL).mock(
        side_effect=[
            httpx.Response(200, json=_chat_response(content="garbage one")),
            httpx.Response(200, json=_chat_response(content="garbage two, still not json")),
        ]
    )
    client = LLMClient(resilient_settings)
    entry = client.chain[0]

    with pytest.raises(LLMOutputError):
        client._complete_structured_with_provider(entry, "system prompt", "say hi", Greeting)


@respx.mock
def test_complete_structured_falls_back_to_secondary_provider(resilient_settings):
    respx.post(GROQ_URL).mock(return_value=httpx.Response(503))
    respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(
            200, json=_chat_response(content=json.dumps({"message": "hi from gemini"}))
        )
    )
    client = LLMClient(resilient_settings)

    result = client.complete_structured("say hi", Greeting)

    assert result.provider == "gemini"
    assert result.value.message == "hi from gemini"


@respx.mock
def test_call_tools_drops_invalid_and_unknown_calls(resilient_settings):
    respx.post(GROQ_URL).mock(
        return_value=httpx.Response(
            200,
            json=_chat_response(
                content=None,
                tool_calls=[
                    {"name": "dummy_tool", "arguments": {"keyword": "ok"}},
                    {"name": "dummy_tool", "arguments": {}},  # missing required field
                    {"name": "unknown_tool", "arguments": {"x": 1}},
                ],
            ),
        )
    )
    client = LLMClient(resilient_settings)

    result = client.call_tools("plan something", [DUMMY_TOOL])

    assert len(result.calls) == 1
    assert result.calls[0].name == "dummy_tool"
    assert result.calls[0].arguments == {"keyword": "ok"}


def test_build_active_chain_skips_provider_without_api_key(test_settings):
    settings = test_settings.model_copy(
        update={
            "llm_chain": "groq:model-a,gemini:model-b",
            "groq_api_key": "a-real-key",
            "gemini_api_key": "",
        }
    )

    chain = build_active_chain(settings)

    assert [entry.provider for entry in chain] == ["groq"]
