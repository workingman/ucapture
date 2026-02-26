"""Retry utility with exponential backoff.

Implements the retry_with_backoff decorator per TDD Section 6, Decision 6.
Supports transient vs permanent failure classification via retryable_exceptions.
"""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable:
    """Decorator for retrying async functions with exponential backoff.

    Delay follows the formula: base_delay * 2^attempt

    Args:
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Base delay in seconds before first retry (default 1.0).
        retryable_exceptions: Tuple of exception types eligible for retry.
            If None, all exceptions are retried (legacy behavior).
            Non-retryable exceptions are re-raised immediately with
            _retry_count attached.

    Returns:
        Decorator that wraps an async function with retry logic.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_error = exc
                    # Permanent failure: re-raise immediately
                    if retryable_exceptions is not None and not isinstance(
                        exc, retryable_exceptions
                    ):
                        exc._retry_count = attempt  # type: ignore[attr-defined]
                        raise
                    if attempt < max_retries:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            "Retry %d/%d for %s after %.1fs: %s",
                            attempt + 1,
                            max_retries,
                            func.__name__,
                            delay,
                            exc,
                        )
                        await asyncio.sleep(delay)
            # Exhausted all retries — attach retry count before raising
            last_error._retry_count = max_retries  # type: ignore[union-attr]
            raise last_error  # type: ignore[misc]

        return wrapper

    return decorator
