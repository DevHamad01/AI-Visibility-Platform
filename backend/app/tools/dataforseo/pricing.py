"""Pre-call cost estimates, derived from DataForSEO's published pricing
(https://dataforseo.com/pricing, https://dataforseo.com/pricing/ai-optimization/llm-mentions,
checked 2026-11-10). These are deliberately *conservative* (rounded up) —
their only job is to stop a call before it's made if it would blow the run
budget; the real cost DataForSEO returns in the response is always what
actually gets recorded.

  keyword_ideas (DataForSEO Labs):      $0.012 /task + $0.00012 /item returned
  search_volume (Keywords Data, live):  $0.09 flat, up to 1000 keywords
  serp_google_organic (live, advanced): $0.002 per ten results + documented modifiers
  llm_mentions_search (AI Optimization, live): $0.10 /request + $0.001 /row
    — by far the most expensive endpoint; CLAUDE.md and the budget guard
    both assume at most one aggregated call per run, never one per query.
"""

from __future__ import annotations

import math
import re


def estimate_keyword_ideas_cost(limit: int) -> float:
    return 0.012 + 0.00012 * limit


def estimate_search_volume_cost() -> float:
    return 0.09


def estimate_serp_google_organic_cost(
    depth: int = 10, *, keyword: str = "", load_async_ai_overview: bool = False
) -> float:
    # Official pricing, checked 2026-11-10:
    # https://dataforseo.com/pricing/google-serp/google-organic-serp-api
    # One live base price per ten results, x5 per paid search operator,
    # plus one base price for an asynchronous AI Overview. Paid PAA
    # expansion is disabled in the tool schema; normal PAA is still parsed.
    operators = re.findall(
        r"\b(?:allinanchor|allintext|allintitle|allinurl|define|filetype|id|inanchor|info|intext|intitle|inurl|link|site)\s*:",
        keyword,
        flags=re.IGNORECASE,
    )
    return 0.002 * (math.ceil(depth / 10) * 5 ** len(operators) + int(load_async_ai_overview))


def estimate_llm_mentions_cost(limit: int) -> float:
    return 0.10 + 0.001 * limit
