"""Retry utility with exponential backoff.

Implements the retry_with_backoff decorator per TDD Section 6, Decision 6.
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0) -> Callable:
    """Decorator for retrying async functions with exponential backoff.

    Delay follows the formula: base_delay * 2^attempt

    Args:
        max_retries: Maximum number of retry attempts (default 3).
        base_delay: Base delay in seconds before first retry (default 1.0).

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
                    if attempt < max_retries:
                        delay = base_delay * (2**attempt)
                        await asyncio.sleep(delay)
            raise last_error  # type: ignore[misc]

        return wrapper

    return decorator
