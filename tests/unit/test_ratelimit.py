"""Tests for rate limiting components."""

import time

import pytest

from yt_tts.core.ratelimit import CircuitBreaker, InvocationBudget, RateLimiter
from yt_tts.exceptions import BudgetExhaustedError


class TestRateLimiter:
    def test_success_resets_failures(self):
        rl = RateLimiter(base_sleep_s=0)
        rl._consecutive_failures = 3
        rl.report_success()
        assert rl._consecutive_failures == 0

    def test_failure_increments(self):
        rl = RateLimiter(base_sleep_s=0, max_retries=5)
        delay = rl.report_failure()
        assert delay > 0
        assert rl._consecutive_failures == 1

    def test_max_retries_exceeded(self):
        rl = RateLimiter(base_sleep_s=0, max_retries=2)
        rl.report_failure()
        rl.report_failure()
        with pytest.raises(BudgetExhaustedError):
            rl.report_failure()

    def test_exponential_backoff(self):
        rl = RateLimiter(base_sleep_s=0, backoff_initial_s=1.0, backoff_multiplier=2.0, max_retries=5)
        d1 = rl.report_failure()
        d2 = rl.report_failure()
        d3 = rl.report_failure()
        assert d1 == 1.0
        assert d2 == 2.0
        assert d3 == 4.0


class TestCircuitBreaker:
    def test_initially_closed(self):
        cb = CircuitBreaker(threshold=3)
        assert not cb.is_open
        cb.check()  # should not raise

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(threshold=2, pause_s=10.0)
        cb.report_failure()
        assert not cb.is_open
        cb.report_failure()
        assert cb.is_open
        with pytest.raises(BudgetExhaustedError):
            cb.check()

    def test_success_resets(self):
        cb = CircuitBreaker(threshold=2, pause_s=10.0)
        cb.report_failure()
        cb.report_success()
        cb.report_failure()
        assert not cb.is_open  # reset after success


class TestInvocationBudget:
    def test_caption_budget(self):
        budget = InvocationBudget(max_caption_fetches=2, max_clip_downloads=10)
        budget.use_caption_fetch()
        budget.use_caption_fetch()
        with pytest.raises(BudgetExhaustedError):
            budget.use_caption_fetch()

    def test_clip_budget(self):
        budget = InvocationBudget(max_caption_fetches=10, max_clip_downloads=2)
        budget.use_clip_download()
        budget.use_clip_download()
        with pytest.raises(BudgetExhaustedError):
            budget.use_clip_download()

    def test_remaining_count(self):
        budget = InvocationBudget(max_caption_fetches=5, max_clip_downloads=3)
        assert budget.caption_fetches_remaining == 5
        budget.use_caption_fetch()
        assert budget.caption_fetches_remaining == 4
        assert budget.clip_downloads_remaining == 3
