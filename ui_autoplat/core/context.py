from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ui_autoplat.config.settings import Settings
from ui_autoplat.core.models import TestCase


@dataclass
class TestContext:
    config: Settings
    shared_data: dict[str, Any] = field(default_factory=dict)
    current_test: TestCase | None = None
    test_params: dict[str, Any] | None = None
