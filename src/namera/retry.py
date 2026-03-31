from __future__ import annotations

import asyncio
import random
import re
from functools import wraps
from typing import Callable

# Patterns that indicate transient/retryable errors
RETRYABLE_PATTERNS = [
    r"timed?\s*out",
    r"connection.*refused",
    r"connection.*reset",
    r"temporary",
    r"i/o\s*timeout",
    r"too many.*request",
    r"rate.?limit",
    r"try again",
    r"service.*unavailable",
    r"503",
    r"429",
]

_retryable_re = re.compile("|".join(RETRYABLE_PATTERNS), re.IGNORECASE)


def is_retryable(error: Exception) -> bool:
    """Check if an exception is likely transient and worth retrying."""
    msg = str(error)
    return bool(_retryable_re.search(msg))


def with_retry(
    max_retries: int = 3,
    initial_backoff: float = 1.0,
    backoff_factor: float = 1.5,
    max_backoff: float = 10.0,
    jitter: bool = True,
) -> Callable:
    """Decorator that retries an async function on transient errors.

    Uses exponential backoff with optional jitter.
    Only retries errors that match RETRYABLE_PATTERNS.
    Non-retryable errors are raised immediately.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            backoff = initial_backoff
            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt == max_retries or not is_retryable(e):
                        raise

                    sleep_time = backoff
                    if jitter:
                        sleep_time = random.uniform(0, backoff)

                    await asyncio.sleep(sleep_time)
                    backoff = min(backoff * backoff_factor, max_backoff)

            raise last_error  # pragma: no cover — should never reach here

        return wrapper

    return decorator
