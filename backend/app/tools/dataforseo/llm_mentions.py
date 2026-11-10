"""`llm_mentions_search` tool: POST /v3/ai_optimization/llm_mentions/search_mentions/live.

CLAUDE.md suggests the older `.../llm_mentions/search/live` path; the current
docs mark that path deprecated (still functional) in favor of
`search_mentions/live`, which this tool uses. Response path per docs:
tasks[0].result[0].items[], with brand/competitor mentions under
`brand_entities` (position/title/category) and cited URLs under `sources`
and `search_results`.

This is by far DataForSEO's most expensive endpoint — $0.10 per request plus
$0.001 per row, versus ~$0.002-0.09 for the others (see pricing.py). `target`
accepts up to 10 keyword/domain entities in **one** request, so a pipeline
run must ask about the brand and every competitor together in a single
aggregated call, never one call per query/competitor — that's the whole
point of this tool taking a list of targets rather than one.

If this endpoint isn't enabled on the account's plan, DataForSEO returns an
auth/plan-class inner status_code, which `DataForSEOClient.post` raises as a
`NonRetryableError` — callers (the pipeline, from Phase 3) catch that and
mark the stage failed with a clear reason; the run continues as `partial`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.llm.types import ToolSpec
from app.tools.dataforseo.client import DataForSEOClient
from app.tools.dataforseo.errors import ToolArgumentError
from app.tools.dataforseo.pricing import estimate_llm_mentions_cost

ENDPOINT = "/v3/ai_optimization/llm_mentions/search_mentions/live"
MAX_TARGETS = 10


class LlmMentionsTarget(BaseModel):
    keyword: str | None = Field(default=None, max_length=250)
    domain: str | None = Field(default=None, max_length=63)

    @model_validator(mode="after")
    def _exactly_one(self) -> LlmMentionsTarget:
        if bool(self.keyword) == bool(self.domain):
            raise ValueError("Each target needs exactly one of keyword or domain.")
        return self

    def to_payload(self) -> dict:
        body: dict = {"search_filter": "include"}
        if self.domain:
            body["domain"] = self.domain
        else:
            body["keyword"] = self.keyword
        return body


class LlmMentionsArgs(BaseModel):
    targets: list[LlmMentionsTarget] = Field(
        ...,
        min_length=1,
        max_length=MAX_TARGETS,
        description="The brand and its competitors, queried together in one call.",
    )
    platform: Literal["google", "chat_gpt"] = "google"
    location_code: int = Field(..., ge=0)
    language_code: str = Field(default="en", min_length=2, max_length=10)
    limit: int = Field(default=10, ge=1, le=1000)


class BrandMention(BaseModel):
    title: str | None = None
    position: int | None = None
    category: str | None = None


class LlmMentionItem(BaseModel):
    platform: str | None = None
    question: str | None = None
    answer: str | None = None
    brand_entities: list[BrandMention]
    source_urls: list[str]


class LlmMentionsResult(BaseModel):
    items: list[LlmMentionItem]
    cost: float


TOOL_SPEC = ToolSpec(
    name="llm_mentions_search",
    description="Search what Google AI Overview or ChatGPT say about a brand and its "
    "competitors together (up to 10 targets in one call), including which brands are "
    "mentioned and which sources are cited. This endpoint is expensive — always pass "
    "every target you need in one call, never call it once per competitor.",
    args_model=LlmMentionsArgs,
)


def llm_mentions_search(
    client: DataForSEOClient, raw_args: dict
) -> LlmMentionsResult | ToolArgumentError:
    try:
        args = LlmMentionsArgs.model_validate(raw_args)
    except ValidationError as exc:
        return ToolArgumentError(tool="llm_mentions_search", errors=exc.errors(), raw_args=raw_args)

    payload = [
        {
            "target": [t.to_payload() for t in args.targets],
            "platform": args.platform,
            "location_code": args.location_code,
            "language_code": args.language_code,
            "limit": args.limit,
        }
    ]
    task = client.post(ENDPOINT, payload, estimated_cost=estimate_llm_mentions_cost(args.limit))
    result0 = (task.get("result") or [{}])[0]
    items = []
    for item in result0.get("items") or []:
        sources = item.get("sources") or []
        search_results = item.get("search_results") or []
        source_urls = [s.get("url") for s in [*sources, *search_results] if s.get("url")]
        brand_entities = [
            BrandMention(
                title=be.get("title"), position=be.get("position"), category=be.get("category")
            )
            for be in item.get("brand_entities") or []
        ]
        items.append(
            LlmMentionItem(
                platform=item.get("platform"),
                question=item.get("question"),
                answer=item.get("answer"),
                brand_entities=brand_entities,
                source_urls=source_urls,
            )
        )
    return LlmMentionsResult(items=items, cost=float(task.get("cost") or 0))
