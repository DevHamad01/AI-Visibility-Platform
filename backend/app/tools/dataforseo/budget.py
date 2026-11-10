"""Per-run DataForSEO spend cap. A trial/sandbox balance is tiny and must
survive the whole project (development + the final demo), not just one run
— so every call is checked against the remaining budget *before* it's made,
using a pricing-docs-derived estimate, and the budget is updated again with
the real `cost` DataForSEO returns.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock

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
    Atomic reservations cover in-flight calls from parallel retrieval nodes.
    Each physical HTTP attempt reserves its estimate; failures release the
    reservation, while every provider-reported charge remains recorded."""

    max_cost_usd: float
    spent_usd: float = field(default=0.0)
    calls: list[tuple[str, float]] = field(default_factory=list)
    _reserved_usd: float = field(default=0.0, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def remaining(self) -> float:
        with self._lock:
            return max(0.0, self.max_cost_usd - self.spent_usd - self._reserved_usd)

    def check(self, endpoint: str, estimated_cost: float) -> None:
        with self._lock:
            if estimated_cost < 0:
                raise ValueError("Estimated cost cannot be negative")
            if estimated_cost > self.remaining() + 1e-12:
                raise BudgetExceededError(endpoint, estimated_cost, self.remaining())

    @contextmanager
    def reserve(self, endpoint: str, estimated_cost: float) -> Iterator[None]:
        with self._lock:
            self.check(endpoint, estimated_cost)
            self._reserved_usd += estimated_cost
        try:
            yield
        finally:
            with self._lock:
                self._reserved_usd = max(0.0, self._reserved_usd - estimated_cost)

    def record_actual_cost(self, endpoint: str, cost: float) -> None:
        with self._lock:
            self.spent_usd += cost
            self.calls.append((endpoint, cost))
        logger.info(
            "dataforseo_budget_spent",
            endpoint=endpoint,
            cost=cost,
            run_spent_usd=round(self.spent_usd, 6),
            run_remaining_usd=round(self.remaining(), 6),
        )
