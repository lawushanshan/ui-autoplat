from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TriggerRunRequest(BaseModel):
    """Request body for triggering a test run."""

    suite_path: str = Field(min_length=1)
    tags: str | list[str] | None = None
    task_name: str | None = None
    async_run: bool = False
    model_config = ConfigDict(extra="forbid")

    @field_validator("suite_path", "task_name")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("must not be empty")
        return text

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, value: str | list[str] | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            tags = [tag.strip() for tag in value.split(",") if tag.strip()]
        else:
            tags = [str(tag).strip() for tag in value if str(tag).strip()]
        return ",".join(tags) if tags else None


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
