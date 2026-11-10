"""Pre-call cost estimates, derived from DataForSEO's published pricing
(https://dataforseo.com/pricing, https://dataforseo.com/pricing/ai-optimization/llm-mentions,
checked 2026-11-10). These are deliberately *conservative* (rounded up) —
their only job is to stop a call before it's made if it would blow the run
budget; the real cost DataForSEO returns in the response is always what
actually gets recorded.

  keyword_ideas (DataForSEO Labs):      $0.012 /task + $0.00012 /item returned
  search_volume (Keywords Data, live):  $0.09 flat, up to 1000 keywords
  serp_google_organic (live, advanced): $0.002 flat per SERP
  llm_mentions_search (AI Optimization, live): $0.10 /request + $0.001 /row
    — by far the most expensive endpoint; CLAUDE.md and the budget guard
    both assume at most one aggregated call per run, never one per query.
"""

from __future__ import annotations


def estimate_keyword_ideas_cost(limit: int) -> float:
    return 0.012 + 0.00012 * limit


def estimate_search_volume_cost() -> float:
    return 0.09


def estimate_serp_google_organic_cost() -> float:
    return 0.002


def estimate_llm_mentions_cost(limit: int) -> float:
    return 0.10 + 0.001 * limit
