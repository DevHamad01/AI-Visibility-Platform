"""`serp_google_organic` tool: POST /v3/serp/google/organic/live/advanced.

Field names per https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/ —
response path tasks[0].result[0].items[], organic rows confirmed as
type: "organic" with rank_group/rank_absolute/domain/title/url/description.

The AI Overview and People Also Ask item shapes are documented
inconsistently (nesting varies by surface / DataForSEO revision), so they're
parsed defensively: any item whose `type` contains "ai_overview" has every
nested "url" collected as a reference; any item whose `type` contains
"people_also_ask" has its question text collected from whichever of
"title"/"question" is present at any depth. An unexpected shape degrades to
an empty list rather than raising.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.llm.types import ToolSpec
from app.tools.dataforseo._json_utils import collect_strings_by_key, find_items_by_type_substring
from app.tools.dataforseo.client import DataForSEOClient
from app.tools.dataforseo.errors import ToolArgumentError
from app.tools.dataforseo.pricing import estimate_serp_google_organic_cost

ENDPOINT = "/v3/serp/google/organic/live/advanced"


class SerpGoogleOrganicArgs(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=700)
    location_code: int = Field(..., ge=0)
    language_code: str = Field(default="en", min_length=2, max_length=10)
    device: Literal["desktop", "mobile"] = "desktop"
    depth: int = Field(default=10, ge=1, le=200)
    people_also_ask_click_depth: int | None = Field(default=None, ge=1, le=4)
    load_async_ai_overview: bool = False


class OrganicResult(BaseModel):
    rank_absolute: int | None = None
    rank_group: int | None = None
    domain: str | None = None
    title: str | None = None
    url: str | None = None
    description: str | None = None


class SerpGoogleOrganicResult(BaseModel):
    organic_results: list[OrganicResult]
    people_also_ask: list[str]
    ai_overview_references: list[str]
    cost: float


TOOL_SPEC = ToolSpec(
    name="serp_google_organic",
    description="Get Google organic search results for a keyword, including AI Overview "
    "references and People Also Ask questions when present.",
    args_model=SerpGoogleOrganicArgs,
)


def serp_google_organic(
    client: DataForSEOClient, raw_args: dict
) -> SerpGoogleOrganicResult | ToolArgumentError:
    try:
        args = SerpGoogleOrganicArgs.model_validate(raw_args)
    except ValidationError as exc:
        return ToolArgumentError(tool="serp_google_organic", errors=exc.errors(), raw_args=raw_args)

    payload = [
        {
            "keyword": args.keyword,
            "location_code": args.location_code,
            "language_code": args.language_code,
            "device": args.device,
            "depth": args.depth,
            **(
                {"people_also_ask_click_depth": args.people_also_ask_click_depth}
                if args.people_also_ask_click_depth is not None
                else {}
            ),
            "load_async_ai_overview": args.load_async_ai_overview,
        }
    ]
    task = client.post(ENDPOINT, payload, estimated_cost=estimate_serp_google_organic_cost())
    result0 = (task.get("result") or [{}])[0]
    items = result0.get("items") or []

    organic_results = [
        OrganicResult(
            rank_absolute=item.get("rank_absolute"),
            rank_group=item.get("rank_group"),
            domain=item.get("domain"),
            title=item.get("title"),
            url=item.get("url"),
            description=item.get("description"),
        )
        for item in items
        if item.get("type") == "organic"
    ]

    paa_items = find_items_by_type_substring(items, "people_also_ask")
    people_also_ask: list[str] = []
    for paa in paa_items:
        people_also_ask.extend(collect_strings_by_key(paa, "title"))
        people_also_ask.extend(collect_strings_by_key(paa, "question"))
    people_also_ask = list(dict.fromkeys(people_also_ask))  # de-dupe, keep order

    ai_overview_items = find_items_by_type_substring(items, "ai_overview")
    ai_overview_references: list[str] = []
    for overview in ai_overview_items:
        ai_overview_references.extend(collect_strings_by_key(overview, "url"))
    ai_overview_references = list(dict.fromkeys(ai_overview_references))

    return SerpGoogleOrganicResult(
        organic_results=organic_results,
        people_also_ask=people_also_ask,
        ai_overview_references=ai_overview_references,
        cost=float(task.get("cost") or 0),
    )
