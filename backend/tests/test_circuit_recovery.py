from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.core.resilience import CircuitBreaker, CircuitOpenError, CircuitState


def test_half_open_allows_only_one_parallel_recovery_probe():
    breaker = CircuitBreaker("recovery-test", failure_threshold=1, cooldown_seconds=0)
    breaker.record_failure()
    barrier = Barrier(2)

    def probe():
        barrier.wait(timeout=5)
        try:
            breaker.before_call()
            return True
        except CircuitOpenError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: probe(), range(2))) == [False, True]
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    breaker.before_call()


def test_local_preflight_failure_releases_the_recovery_probe():
    breaker = CircuitBreaker("preflight-test", failure_threshold=1, cooldown_seconds=0)
    breaker.record_failure()
    breaker.before_call()
    breaker.cancel_probe()
    breaker.before_call()
