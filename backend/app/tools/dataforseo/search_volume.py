"""`search_volume` tool: POST /v3/keywords_data/google_ads/search_volume/live.

Field names per https://docs.dataforseo.com/v3/keywords_data/google_ads/search_volume/live/ —
response path tasks[0].result[] (no extra "items" nesting, unlike the Labs
and SERP endpoints), with both a string `competition` and a numeric
`competition_index` (0-100).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from app.llm.types import ToolSpec
from app.tools.dataforseo.client import DataForSEOClient
from app.tools.dataforseo.errors import ToolArgumentError

ENDPOINT = "/v3/keywords_data/google_ads/search_volume/live"


class SearchVolumeArgs(BaseModel):
    keywords: list[str] = Field(..., min_length=1, max_length=1000)
    location_code: int = Field(..., ge=0)
    language_code: str = Field(default="en", min_length=2, max_length=10)


class SearchVolumeItem(BaseModel):
    keyword: str
    search_volume: int | None = None
    competition: str | None = None
    competition_index: int | None = None
    cpc: float | None = None
    low_top_of_page_bid: float | None = None
    high_top_of_page_bid: float | None = None


class SearchVolumeResult(BaseModel):
    items: list[SearchVolumeItem]
    cost: float


TOOL_SPEC = ToolSpec(
    name="search_volume",
    description="Get monthly search volume, competition and CPC for exact keywords.",
    args_model=SearchVolumeArgs,
)


def search_volume(client: DataForSEOClient, raw_args: dict) -> SearchVolumeResult | ToolArgumentError:
    try:
        args = SearchVolumeArgs.model_validate(raw_args)
    except ValidationError as exc:
        return ToolArgumentError(tool="search_volume", errors=exc.errors(), raw_args=raw_args)

    payload = [
        {
            "keywords": args.keywords,
            "location_code": args.location_code,
            "language_code": args.language_code,
        }
    ]
    task = client.post(ENDPOINT, payload)
    items = [
        SearchVolumeItem(
            keyword=row.get("keyword", ""),
            search_volume=row.get("search_volume"),
            competition=row.get("competition"),
            competition_index=row.get("competition_index"),
            cpc=row.get("cpc"),
            low_top_of_page_bid=row.get("low_top_of_page_bid"),
            high_top_of_page_bid=row.get("high_top_of_page_bid"),
        )
        for row in task.get("result") or []
        if row
    ]
    return SearchVolumeResult(items=items, cost=float(task.get("cost") or 0))
