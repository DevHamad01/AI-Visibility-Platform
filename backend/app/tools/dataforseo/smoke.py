"""Live smoke test: `python -m app.tools.dataforseo.smoke "<query>"`.

Calls serp_google_organic + keyword_ideas for real against DataForSEO and
prints a short summary, so real credentials and response parsing can be
verified by eye. Not part of the automated test suite (those mock HTTP).
"""

from __future__ import annotations

import sys

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import init_engine
from app.tools.dataforseo.client import DataForSEOClient
from app.tools.dataforseo.errors import ToolArgumentError
from app.tools.dataforseo.keyword_ideas import keyword_ideas
from app.tools.dataforseo.serp_google_organic import serp_google_organic

logger = get_logger(__name__)

DEFAULT_LOCATION_CODE = 2840  # United States


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('Usage: python -m app.tools.dataforseo.smoke "<query>"', file=sys.stderr)
        return 2
    query = argv[1]

    settings = get_settings()
    configure_logging(settings.log_level)

    if not settings.dataforseo_login or not settings.dataforseo_password:
        print("DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD are not set — nothing to smoke test.", file=sys.stderr)
        return 1

    init_engine(settings.database_url)
    client = DataForSEOClient(settings)

    print(f"--- serp_google_organic: {query!r} ---")
    serp_result = serp_google_organic(
        client,
        {
            "keyword": query,
            "location_code": DEFAULT_LOCATION_CODE,
            "language_code": "en",
            "people_also_ask_click_depth": 1,
            "load_async_ai_overview": True,
        },
    )
    if isinstance(serp_result, ToolArgumentError):
        print(f"ARGUMENT ERROR: {serp_result.errors}")
    else:
        print(f"cost=${serp_result.cost:.5f}  organic_results={len(serp_result.organic_results)}")
        for row in serp_result.organic_results[:5]:
            print(f"  #{row.rank_absolute:<3} {row.domain:<30} {row.title}")
        print(f"  people_also_ask ({len(serp_result.people_also_ask)}): {serp_result.people_also_ask[:3]}")
        print(f"  ai_overview_references ({len(serp_result.ai_overview_references)}): "
              f"{serp_result.ai_overview_references[:3]}")

    print(f"\n--- keyword_ideas: {query!r} ---")
    keyword_result = keyword_ideas(
        client,
        {
            "keywords": [query],
            "location_code": DEFAULT_LOCATION_CODE,
            "language_code": "en",
            "limit": 5,
        },
    )
    if isinstance(keyword_result, ToolArgumentError):
        print(f"ARGUMENT ERROR: {keyword_result.errors}")
    else:
        print(f"cost=${keyword_result.cost:.5f}  items={len(keyword_result.items)}")
        for idea in keyword_result.items[:5]:
            print(
                f"  {idea.keyword!r:<40} volume={idea.search_volume} "
                f"competition={idea.competition} cpc={idea.cpc} difficulty={idea.keyword_difficulty}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
