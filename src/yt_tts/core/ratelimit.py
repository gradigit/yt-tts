"""Rate limiting, circuit breaker, and budget tracking."""

import threading
import time

from yt_tts.exceptions import BudgetExhaustedError


class RateLimiter:
    """Per-source sleep intervals with exponential backoff on 429s."""

    def __init__(
        self,
        base_sleep_s: float = 2.0,
        backoff_initial_s: float = 2.0,
        backoff_multiplier: float = 2.0,
        backoff_max_s: float = 60.0,
        max_retries: int = 5,
    ):
        self.base_sleep_s = base_sleep_s
        self.backoff_initial_s = backoff_initial_s
        self.backoff_multiplier = backoff_multiplier
        self.backoff_max_s = backoff_max_s
        self.max_retries = max_retries
        self._lock = threading.Lock()
        self._last_call: float = 0.0
        self._consecutive_failures: int = 0

    def wait(self) -> None:
        """Wait the appropriate interval before the next call."""
        with self._lock:
            elapsed = time.monotonic() - self._last_call
            sleep_time = self.base_sleep_s - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._last_call = time.monotonic()

    def report_success(self) -> None:
        """Reset backoff state after a successful call."""
        with self._lock:
            self._consecutive_failures = 0

    def report_failure(self) -> float:
        """Record a failure and return the backoff delay in seconds.

        Raises BudgetExhaustedError if max retries exceeded.
        """
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures > self.max_retries:
                raise BudgetExhaustedError(f"Max retries ({self.max_retries}) exceeded")
            delay = min(
                self.backoff_initial_s
                * (self.backoff_multiplier ** (self._consecutive_failures - 1)),
                self.backoff_max_s,
            )
            return delay

    def backoff_wait(self) -> None:
        """Wait with exponential backoff after a failure."""
        delay = self.report_failure()
        time.sleep(delay)


class CircuitBreaker:
    """Pauses requests to a source after consecutive failures."""

    def __init__(self, threshold: int = 3, pause_s: float = 300.0):
        self.threshold = threshold
        self.pause_s = pause_s
        self._lock = threading.Lock()
        self._consecutive_failures: int = 0
        self._open_until: float = 0.0

    @property
    def is_open(self) -> bool:
        """True if the circuit is open (requests should not be made)."""
        return time.monotonic() < self._open_until

    def check(self) -> None:
        """Check if the circuit is open. Raises BudgetExhaustedError if so."""
        if self.is_open:
            remaining = self._open_until - time.monotonic()
            raise BudgetExhaustedError(f"Circuit breaker open, retry in {remaining:.0f}s")

    def report_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0

    def report_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.threshold:
                self._open_until = time.monotonic() + self.pause_s


class InvocationBudget:
    """Tracks resource usage within a single synthesis invocation."""

    def __init__(self, max_caption_fetches: int = 50, max_clip_downloads: int = 30):
        self.max_caption_fetches = max_caption_fetches
        self.max_clip_downloads = max_clip_downloads
        self._lock = threading.Lock()
        self._caption_fetches: int = 0
        self._clip_downloads: int = 0

    def use_caption_fetch(self) -> None:
        with self._lock:
            self._caption_fetches += 1
            if self._caption_fetches > self.max_caption_fetches:
                raise BudgetExhaustedError(
                    f"Caption fetch budget exhausted ({self.max_caption_fetches})"
                )

    def use_clip_download(self) -> None:
        with self._lock:
            self._clip_downloads += 1
            if self._clip_downloads > self.max_clip_downloads:
                raise BudgetExhaustedError(
                    f"Clip download budget exhausted ({self.max_clip_downloads})"
                )

    @property
    def caption_fetches_remaining(self) -> int:
        return max(0, self.max_caption_fetches - self._caption_fetches)

    @property
    def clip_downloads_remaining(self) -> int:
        return max(0, self.max_clip_downloads - self._clip_downloads)
