"""`keyword_ideas` tool: POST /v3/dataforseo_labs/google/keyword_ideas/live.

Field names per https://docs.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live/ —
response path tasks[0].result[0].items[], with volume/competition/cpc under
`keyword_info` and difficulty under the separate `keyword_properties` object.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from app.llm.types import ToolSpec
from app.tools.dataforseo.client import DataForSEOClient
from app.tools.dataforseo.errors import ToolArgumentError
from app.tools.dataforseo.pricing import estimate_keyword_ideas_cost

ENDPOINT = "/v3/dataforseo_labs/google/keyword_ideas/live"


class KeywordIdeasArgs(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=200, description="Seed keywords.")
    location_code: int = Field(..., ge=0, description="DataForSEO location code, e.g. 2840 for the US.")
    language_code: str = Field(default="en", min_length=2, max_length=10)
    limit: int = Field(default=50, ge=1, le=1000)


class KeywordIdea(BaseModel):
    keyword: str
    search_volume: int | None = None
    competition: float | None = None
    competition_level: str | None = None
    cpc: float | None = None
    keyword_difficulty: int | None = None


class KeywordIdeasResult(BaseModel):
    items: list[KeywordIdea]
    cost: float


TOOL_SPEC = ToolSpec(
    name="keyword_ideas",
    description="Get related keyword ideas with search volume, competition and difficulty.",
    args_model=KeywordIdeasArgs,
)


def keyword_ideas(
    client: DataForSEOClient, raw_args: dict
) -> KeywordIdeasResult | ToolArgumentError:
    try:
        args = KeywordIdeasArgs.model_validate(raw_args)
    except ValidationError as exc:
        return ToolArgumentError(tool="keyword_ideas", errors=exc.errors(), raw_args=raw_args)

    payload = [
        {
            "keywords": args.keywords,
            "location_code": args.location_code,
            "language_code": args.language_code,
            "limit": args.limit,
        }
    ]
    task = client.post(ENDPOINT, payload, estimated_cost=estimate_keyword_ideas_cost(args.limit))
    result0 = (task.get("result") or [{}])[0]
    items = []
    for item in result0.get("items") or []:
        keyword_info = item.get("keyword_info") or {}
        keyword_properties = item.get("keyword_properties") or {}
        items.append(
            KeywordIdea(
                keyword=item.get("keyword", ""),
                search_volume=keyword_info.get("search_volume"),
                competition=keyword_info.get("competition"),
                competition_level=keyword_info.get("competition_level"),
                cpc=keyword_info.get("cpc"),
                keyword_difficulty=keyword_properties.get("keyword_difficulty"),
            )
        )
    return KeywordIdeasResult(items=items, cost=float(task.get("cost") or 0))
