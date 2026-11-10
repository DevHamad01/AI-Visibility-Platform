"""Every LLM prompt used by the pipeline, in one module (CLAUDE.md section 4
item 2): specific, short, grounded in the brand snapshot, with an explicit
output shape and an explicit instruction never to invent numbers — those
only ever come from DataForSEO + the deterministic scorer.
"""

from __future__ import annotations

from app.pipeline.schemas import GapAnalysisBatch, RecommendationsBatch

# --- QueryPlanner ------------------------------------------------------------


def query_planner_system_prompt() -> str:
    return (
        "You are a search-visibility research planner. You choose which data-collection "
        "tools to call and with what arguments — you never invent search volumes, rankings, "
        "or any other number yourself; those only ever come from the tools' real responses."
    )


def query_planner_user_prompt(
    brand_snapshot: dict,
    *,
    max_queries: int,
    max_serp_calls: int,
    location_code: int,
    language_code: str,
) -> str:
    competitors = brand_snapshot.get("competitors") or []
    competitor_lines = "\n".join(f"  - {c['name']} ({c['domain']})" for c in competitors)
    return f"""
Brand: {brand_snapshot["name"]} ({brand_snapshot["domain"]})
Industry: {brand_snapshot.get("industry") or "unknown"}
Competitors:
{competitor_lines or "  (none tracked)"}

Every tool call's location_code must be exactly {location_code} and language_code must be
exactly "{language_code}".

Call these tools:
1. `keyword_ideas` — exactly ONE call. Seed it with 2-4 short phrases describing what this
   brand sells or the problem it solves (not the brand name itself). Set limit to {max_queries}.
2. `serp_google_organic` — up to {max_serp_calls} calls, one per realistic buyer-intent search
   query a prospective customer of this brand would type into Google (e.g. "best X for Y",
   "X vs Y", "X pricing", "X alternatives"). Every query must be different. Set
   people_also_ask_click_depth to 1 and load_async_ai_overview to true on every call.
3. `llm_mentions_search` — exactly ONE call, combining every target into that single call.
   Its `targets` list must have one entry for the brand's own domain
   ({brand_snapshot["domain"]}) and one entry for each competitor's domain listed above
   (up to 10 targets total). Never call this tool more than once.
""".strip()


# --- GapAnalyst --------------------------------------------------------------


def gap_analyst_system_prompt() -> str:
    return (
        "You analyze search-visibility gaps for a brand. For each query you are given, "
        "classify its search intent and explain in 1-2 sentences, using ONLY the numbers "
        "provided (visibility, contested share, difficulty, search volume), why this specific "
        "gap exists. Never invent a number you were not given, and never claim data that isn't "
        f"in the input. Respond with a JSON object matching this exact shape: "
        f"{GapAnalysisBatch.model_json_schema()}"
    )


def gap_analyst_user_prompt(opportunities: list[dict]) -> str:
    lines = []
    for opp in opportunities:
        lines.append(
            f"- query_id={opp['query_id']!r} text={opp['text']!r} search_volume="
            f"{opp['search_volume']} score={opp['score']} visibility={opp['visibility']} "
            f"gap={opp['gap']} contested={opp['contested']} difficulty={opp['difficulty']}"
        )
    return "Opportunities (highest score first):\n" + "\n".join(lines)


# --- Recommender --------------------------------------------------------------


def recommender_system_prompt() -> str:
    return (
        "You write content recommendations to close search-visibility gaps for a brand. For "
        "each opportunity you are given, propose ONE piece of content (title, content type, a "
        "short outline, why it matters, priority and effort) that would help this brand close "
        "that specific gap. Never invent a number you were not given. Respond with a JSON "
        f"object matching this exact shape: {RecommendationsBatch.model_json_schema()}"
    )


def recommender_user_prompt(brand_snapshot: dict, opportunities: list[dict]) -> str:
    lines = []
    for opp in opportunities:
        lines.append(
            f"- query_id={opp['query_id']!r} text={opp['text']!r} intent={opp.get('intent')} "
            f"score={opp['score']} explanation={opp.get('explanation')!r}"
        )
    return (
        f"Brand: {brand_snapshot['name']} ({brand_snapshot['domain']})\n"
        "Opportunities to address (highest score first):\n" + "\n".join(lines)
    )
