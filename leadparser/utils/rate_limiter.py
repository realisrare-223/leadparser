"""
Rate Limiter — enforces polite delays between scraping requests.

Uses configurable min/max random delays to mimic human browsing
behavior and avoid triggering anti-bot measures.
"""

import time
import random
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Randomized delay enforcer for respectful web scraping.
    All delays are configurable via config.yaml under scraping.delay_min
    and scraping.delay_max.
    """

    def __init__(self, config: dict):
        self.delay_min: float = config["scraping"].get("delay_min", 2.5)
        self.delay_max: float = config["scraping"].get("delay_max", 6.0)
        self._last_request_time: float = 0.0

    # ── Core wait method ──────────────────────────────────────────────

    def wait(self, override_min: float = None, override_max: float = None) -> None:
        """
        Sleep for a random duration between [min, max] seconds.

        Can be called with explicit bounds to override the defaults —
        useful for shorter pauses between sub-actions within a page.
        """
        lo = override_min if override_min is not None else self.delay_min
        hi = override_max if override_max is not None else self.delay_max
        delay = random.uniform(lo, hi)
        logger.debug(f"Rate limiter sleeping {delay:.2f}s")
        time.sleep(delay)
        self._last_request_time = time.time()

    def wait_short(self) -> None:
        """Quick micro-pause (0.5–1.5 s) between in-page interactions."""
        self.wait(0.5, 1.5)

    def wait_long(self) -> None:
        """Longer cooldown (8–15 s) after consecutive failures or CAPTCHA hints."""
        self.wait(8.0, 15.0)

    # ── Decorator ────────────────────────────────────────────────────

    def limit(self, func):
        """
        Decorator: automatically enforce a rate-limit delay before
        the wrapped function executes.

        Usage:
            @rate_limiter.limit
            def fetch_page(url): ...
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait()
            return func(*args, **kwargs)
        return wrapper

    # ── Adaptive back-off ─────────────────────────────────────────────

    def backoff(self, attempt: int) -> None:
        """
        Exponential back-off with jitter for retry logic.

        attempt 1 → ~2–4 s
        attempt 2 → ~4–8 s
        attempt 3 → ~8–16 s
        """
        base = 2.0 ** attempt
        jitter = random.uniform(0, base * 0.5)
        delay = base + jitter
        logger.info(f"Back-off delay: {delay:.1f}s (attempt {attempt})")
        time.sleep(delay)
