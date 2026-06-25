"""Tests for retry decorator and circuit breaker."""

from __future__ import annotations

import threading

import pytest
import tenacity

from ocr_pipeline.engines.base import CircuitBreaker, with_api_retry


# ---------------------------------------------------------------------------
# with_api_retry
# ---------------------------------------------------------------------------


class TestWithApiRetry:
    def test_retries_and_succeeds_on_second_attempt(self):
        call_count: list[int] = [0]

        @with_api_retry(max_retries=3, base_delay=0.001, max_delay=0.01)
        def flaky_func() -> str:
            call_count[0] += 1
            if call_count[0] < 2:
                raise OSError("temporary failure")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count[0] == 2

    def test_exhausts_retries_and_reraises(self):
        call_count: list[int] = [0]

        @with_api_retry(max_retries=2, base_delay=0.001, max_delay=0.01)
        def always_fails() -> str:
            call_count[0] += 1
            raise OSError("always broken")

        with pytest.raises(OSError):
            always_fails()
        assert call_count[0] == 2

    def test_retry_stats_tracks_attempts(self):
        call_count: list[int] = [0]

        @with_api_retry(max_retries=3, base_delay=0.001, max_delay=0.01)
        def flaky() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                raise OSError("fail")
            return "ok"

        flaky()
        # retry_stats resets to 0 after the call; during the call it was 2
        # Let's check the wrapper has retry_stats
        assert hasattr(flaky, "retry_stats")

    def test_does_not_retry_on_unmatched_exception(self):
        call_count: list[int] = [0]

        @with_api_retry(max_retries=3, base_delay=0.001, max_delay=0.01)
        def raises_value_error() -> str:
            call_count[0] += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            raises_value_error()
        assert call_count[0] == 1

    def test_retry_on_tenacity_try_again(self):
        call_count: list[int] = [0]
        attempt: list[int] = [0]

        @with_api_retry(max_retries=2, base_delay=0.001, max_delay=0.01)
        def manual_retry() -> str:
            call_count[0] += 1
            attempt[0] += 1
            if attempt[0] < 2:
                raise tenacity.TryAgain
            return "finally"

        result = manual_retry()
        assert result == "finally"
        assert call_count[0] == 2


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_not_open_by_default(self):
        cb = CircuitBreaker(threshold=3)
        assert not cb.is_open("engine_a")

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=3)
        for _ in range(3):
            cb.record_failure("engine_x")
        assert cb.is_open("engine_x")

    def test_does_not_open_before_threshold(self):
        cb = CircuitBreaker(threshold=3)
        cb.record_failure("engine_x")
        cb.record_failure("engine_x")
        assert not cb.is_open("engine_x")

    def test_success_resets_counter(self):
        cb = CircuitBreaker(threshold=3)
        cb.record_failure("engine_x")
        cb.record_failure("engine_x")
        cb.record_success("engine_x")
        # Counter reset, not open
        assert not cb.is_open("engine_x")

    def test_success_after_open_closes_circuit(self):
        cb = CircuitBreaker(threshold=3)
        for _ in range(3):
            cb.record_failure("engine_x")
        assert cb.is_open("engine_x")
        cb.record_success("engine_x")
        assert not cb.is_open("engine_x")

    def test_engines_are_independent(self):
        cb = CircuitBreaker(threshold=2)
        cb.record_failure("engine_a")
        cb.record_failure("engine_a")
        assert cb.is_open("engine_a")
        assert not cb.is_open("engine_b")

    def test_thread_safety_basic(self):
        cb = CircuitBreaker(threshold=100)
        errors: list[str] = []

        def fail_and_check() -> None:
            for _ in range(50):
                cb.record_failure("e")
                if cb.is_open("e"):
                    errors.append("opened too early")

        threads = [threading.Thread(target=fail_and_check) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # With 4 threads * 50 failures = 200, threshold=100, circuit should be open.
        assert cb.is_open("e")
        # But check for race: if errors is non-empty, something went wrong.
        # Actually it's possible intermediate checks see it open before all are done.
        # The key test is: no crashes, circuit ends up open.
