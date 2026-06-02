from __future__ import annotations

from datetime import datetime
from typing import Any


class TriggerRunRequest:
    """Request body for triggering a test run."""

    def __init__(self, suite_path: str, tags: list[str] | None = None, task_name: str | None = None) -> None:
        self.suite_path = suite_path
        self.tags = tags or []
        self.task_name = task_name


class TriggerRunResponse:
    def __init__(self, run_id: str, status: str, test_count: int) -> None:
        self.run_id = run_id
        self.status = status
        self.test_count = test_count


class TestResultResponse:
    def __init__(self, name: str, suite: str, status: str, duration: float, error: str | None = None) -> None:
        self.name = name
        self.suite = suite
        self.status = status
        self.duration = duration
        self.error = error


class TestRunResponse:
    def __init__(
        self,
        run_id: str,
        timestamp: str,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        duration: float,
        pass_rate: float,
        results: list[TestResultResponse] | None = None,
    ) -> None:
        self.run_id = run_id
        self.timestamp = timestamp
        self.total = total
        self.passed = passed
        self.failed = failed
        self.skipped = skipped
        self.duration = duration
        self.pass_rate = pass_rate
        self.results = results


class HistoryResponse:
    def __init__(self, test_name: str, trend: list[dict[str, Any]], flaky: list[dict[str, Any]]) -> None:
        self.test_name = test_name
        self.trend = trend
        self.flaky = flaky


class SuiteInfo:
    def __init__(self, name: str, file_path: str, test_count: int, tags: list[str]) -> None:
        self.name = name
        self.file_path = file_path
        self.test_count = test_count
        self.tags = tags
