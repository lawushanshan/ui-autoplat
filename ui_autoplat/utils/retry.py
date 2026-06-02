from __future__ import annotations

import functools
import time
from typing import Callable, Sequence, Type


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Sequence[Type[Exception]] | None = None,
) -> Callable:
    if exceptions is None:
        exceptions = (Exception,)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
