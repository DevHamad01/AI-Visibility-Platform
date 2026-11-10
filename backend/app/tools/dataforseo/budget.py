"""Per-run DataForSEO spend cap. A trial/sandbox balance is tiny and must
survive the whole project (development + the final demo), not just one run
— so every call is checked against the remaining budget *before* it's made,
using a pricing-docs-derived estimate, and the budget is updated again with
the real `cost` DataForSEO returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


class BudgetExceededError(Exception):
    def __init__(self, endpoint: str, estimated_cost: float, remaining: float) -> None:
        super().__init__(
            f"Estimated cost ${estimated_cost:.4f} for {endpoint} would exceed the "
            f"remaining run budget of ${remaining:.4f}."
        )
        self.endpoint = endpoint
        self.estimated_cost = estimated_cost
        self.remaining = remaining


@dataclass
class RunBudget:
    """Tracks one analysis run's cumulative DataForSEO spend against a cap.
    Not thread-safe by design — one run, one budget, used from one worker job."""

    max_cost_usd: float
    spent_usd: float = field(default=0.0)
    calls: list[tuple[str, float]] = field(default_factory=list)

    def remaining(self) -> float:
        return max(0.0, self.max_cost_usd - self.spent_usd)

    def check(self, endpoint: str, estimated_cost: float) -> None:
        if self.spent_usd + estimated_cost > self.max_cost_usd:
            raise BudgetExceededError(endpoint, estimated_cost, self.remaining())

    def record_actual_cost(self, endpoint: str, cost: float) -> None:
        self.spent_usd += cost
        self.calls.append((endpoint, cost))
        logger.info(
            "dataforseo_budget_spent",
            endpoint=endpoint,
            cost=cost,
            run_spent_usd=round(self.spent_usd, 6),
            run_remaining_usd=round(self.remaining(), 6),
        )
