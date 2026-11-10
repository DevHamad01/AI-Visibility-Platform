"""Live smoke test: `python -m app.tools.dataforseo.smoke "<query>"`.

Calls serp_google_organic + keyword_ideas for real against DataForSEO (the
smallest requests that still exercise AI Overview / People Also Ask
parsing), prints account balance before/after via the free user_data
endpoint, and enforces the same per-run budget guard (DATAFORSEO_MAX_COST_PER_RUN)
a pipeline run would use. Not part of the automated test suite (those mock
HTTP) — this is for verifying real credentials and response parsing by eye.

Deliberately does NOT call llm_mentions_search here: at $0.10/request +
$0.001/row it's by far the most expensive endpoint (see pricing.py) and a
trial balance should not be spent on a routine smoke check.
"""

from __future__ import annotations

import sys
from typing import Any

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.resilience import CircuitOpenError, NonRetryableError, RetryableError
from app.db.base import init_engine
from app.tools.dataforseo.budget import BudgetExceededError, RunBudget
from app.tools.dataforseo.client import DataForSEOClient
from app.tools.dataforseo.errors import ToolArgumentError
from app.tools.dataforseo.keyword_ideas import keyword_ideas
from app.tools.dataforseo.serp_google_organic import serp_google_organic

logger = get_logger(__name__)

DEFAULT_LOCATION_CODE = 2840  # United States

# A call can fail without ever reaching the cost-bearing part of DataForSEO
# (e.g. account not verified, auth rejected, circuit open from an earlier
# failure in this same run) — the smoke CLI reports that clearly and moves
# on instead of crashing, same as a Phase 3 pipeline node would.
_CALL_FAILURE_TYPES = (BudgetExceededError, RetryableError, NonRetryableError, CircuitOpenError)


def _extract_balance(user_data_task: dict[str, Any]) -> float | None:
    """Defensive lookup of result[0].money.balance — falls back to scanning
    for any "balance" key if the account/account-tier response is shaped
    differently than documented."""
    result0 = (user_data_task.get("result") or [{}])[0]
    money = result0.get("money")
    if isinstance(money, dict) and "balance" in money:
        return money["balance"]

    def _search(obj: Any) -> float | None:
        if isinstance(obj, dict):
            if "balance" in obj:
                return obj["balance"]
            for value in obj.values():
                found = _search(value)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = _search(value)
                if found is not None:
                    return found
        return None

    return _search(result0)


def _print_balance(client: DataForSEOClient, label: str) -> float | None:
    try:
        task = client.get_user_data()
    except Exception as exc:  # noqa: BLE001 — this is a diagnostic print, never fatal
        print(f"{label} balance: COULD NOT FETCH ({exc})")
        return None
    if task.get("status_code") not in (20000, None):
        print(
            f"{label} balance: user_data returned status "
            f"{task.get('status_code')}: {task.get('status_message')}"
        )
        return None
    balance = _extract_balance(task)
    if balance is not None:
        print(f"{label} balance: ${balance:.4f}")
    else:
        print(f"{label} balance: field not found (raw task: {task})")
    return balance


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
    budget = RunBudget(max_cost_usd=settings.dataforseo_max_cost_per_run)
    client = DataForSEOClient(settings, budget=budget)

    print(f"Base URL: {settings.dataforseo_base_url}")
    print(f"Run budget cap: ${settings.dataforseo_max_cost_per_run:.4f}\n")

    balance_before = _print_balance(client, "BEFORE")

    print(f"\n--- serp_google_organic: {query!r} (depth=1, minimal) ---")
    try:
        serp_result = serp_google_organic(
            client,
            {
                "keyword": query,
                "location_code": DEFAULT_LOCATION_CODE,
                "language_code": "en",
                "depth": 1,
                "people_also_ask_click_depth": 1,
                "load_async_ai_overview": True,
            },
        )
    except _CALL_FAILURE_TYPES as exc:
        print(f"CALL FAILED ({type(exc).__name__}): {exc}")
        serp_result = None

    if isinstance(serp_result, ToolArgumentError):
        print(f"ARGUMENT ERROR: {serp_result.errors}")
    elif serp_result is not None:
        print(f"cost=${serp_result.cost:.5f}  organic_results={len(serp_result.organic_results)}")
        for row in serp_result.organic_results[:5]:
            print(f"  #{row.rank_absolute:<3} {row.domain:<30} {row.title}")
        print(f"  people_also_ask ({len(serp_result.people_also_ask)}): {serp_result.people_also_ask[:3]}")
        print(
            f"  ai_overview_references ({len(serp_result.ai_overview_references)}): "
            f"{serp_result.ai_overview_references[:3]}"
        )

    print(f"\n--- keyword_ideas: {query!r} (limit=1, minimal) ---")
    try:
        keyword_result = keyword_ideas(
            client,
            {
                "keywords": [query],
                "location_code": DEFAULT_LOCATION_CODE,
                "language_code": "en",
                "limit": 1,
            },
        )
    except _CALL_FAILURE_TYPES as exc:
        print(f"CALL FAILED ({type(exc).__name__}): {exc}")
        keyword_result = None

    if isinstance(keyword_result, ToolArgumentError):
        print(f"ARGUMENT ERROR: {keyword_result.errors}")
    elif keyword_result is not None:
        print(f"cost=${keyword_result.cost:.5f}  items={len(keyword_result.items)}")
        for idea in keyword_result.items[:5]:
            print(
                f"  {idea.keyword!r:<40} volume={idea.search_volume} "
                f"competition={idea.competition} cpc={idea.cpc} difficulty={idea.keyword_difficulty}"
            )

    print()
    balance_after = _print_balance(client, "AFTER")

    print(
        f"\nRun budget spent (tracked): ${budget.spent_usd:.5f} of "
        f"${settings.dataforseo_max_cost_per_run:.4f}"
    )
    if balance_before is not None and balance_after is not None:
        print(f"Balance delta (BEFORE - AFTER): ${balance_before - balance_after:.5f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
