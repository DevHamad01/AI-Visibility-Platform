"""Real simultaneous calls exercise reservation safety, without external APIs."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest

from app.tools.dataforseo.budget import BudgetExceededError, RunBudget


def test_parallel_call_cannot_spend_an_inflight_reservation():
    budget = RunBudget(max_cost_usd=0.15)
    ready = Barrier(2)
    release = Event()

    def first_call():
        with budget.reserve("first", 0.10):
            ready.wait(timeout=5)
            assert release.wait(timeout=5)
            budget.record_actual_cost("first", 0.10)

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(first_call)
        ready.wait(timeout=5)
        try:
            with pytest.raises(BudgetExceededError):
                with budget.reserve("second", 0.10):
                    pytest.fail("The second request must not start")
        finally:
            release.set()
        first.result(timeout=5)
    assert budget.spent_usd == pytest.approx(0.10)
    assert budget.remaining() == pytest.approx(0.05)


def test_failed_attempt_releases_estimate_without_discarding_actual_charge():
    budget = RunBudget(max_cost_usd=0.15)
    with pytest.raises(RuntimeError):
        with budget.reserve("attempt", 0.10):
            budget.record_actual_cost("attempt", 0.02)
            raise RuntimeError("Billed task returned an error")
    assert budget.remaining() == pytest.approx(0.13)
    with budget.reserve("next", 0.12):
        pass
