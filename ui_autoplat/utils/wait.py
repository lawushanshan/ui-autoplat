from __future__ import annotations

import time
from typing import Callable


def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    error_message: str = "Condition not met within timeout",
) -> None:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if condition():
            return
        time.sleep(poll_interval)
    raise TimeoutError(error_message)
