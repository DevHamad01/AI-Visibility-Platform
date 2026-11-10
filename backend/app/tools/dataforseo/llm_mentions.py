"""`llm_mentions_search` tool: POST /v3/ai_optimization/llm_mentions/search_mentions/live.

CLAUDE.md suggests the older `.../llm_mentions/search/live` path; the current
docs mark that path deprecated (still functional) in favor of
`search_mentions/live`, which this tool uses. Response path per docs:
tasks[0].result[0].items[], with brand/competitor mentions under
`brand_entities` (position/title/category) and cited URLs under `sources`
and `search_results`.

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

ENDPOINT = "/v3/ai_optimization/llm_mentions/search_mentions/live"


class LlmMentionsArgs(BaseModel):
    target_keyword: str | None = Field(default=None, max_length=250)
    target_domain: str | None = Field(default=None, max_length=63)
    platform: Literal["google", "chat_gpt"] = "google"
    location_code: int = Field(..., ge=0)
    language_code: str = Field(default="en", min_length=2, max_length=10)
    limit: int = Field(default=10, ge=1, le=1000)

    @model_validator(mode="after")
    def _one_target_required(self) -> LlmMentionsArgs:
        if not self.target_keyword and not self.target_domain:
            raise ValueError("One of target_keyword or target_domain is required.")
        return self


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
    description="Search what Google AI Overview or ChatGPT say about a brand or topic, "
    "including which brands are mentioned and which sources are cited.",
    args_model=LlmMentionsArgs,
)


def llm_mentions_search(
    client: DataForSEOClient, raw_args: dict
) -> LlmMentionsResult | ToolArgumentError:
    try:
        args = LlmMentionsArgs.model_validate(raw_args)
    except ValidationError as exc:
        return ToolArgumentError(tool="llm_mentions_search", errors=exc.errors(), raw_args=raw_args)

    target: dict = {"search_filter": "include"}
    if args.target_domain:
        target["domain"] = args.target_domain
    else:
        target["keyword"] = args.target_keyword

    payload = [
        {
            "target": [target],
            "platform": args.platform,
            "location_code": args.location_code,
            "language_code": args.language_code,
            "limit": args.limit,
        }
    ]
    task = client.post(ENDPOINT, payload)
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
