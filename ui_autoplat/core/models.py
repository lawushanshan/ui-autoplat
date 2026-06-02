from __future__ import annotations

import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal


@dataclass
class TestStep:
    name: str
    status: Literal["passed", "failed"]
    duration: float
    screenshot: Path | None = None


@dataclass
class TestCase:
    name: str
    function: Callable[..., Any]
    file_path: Path
    suite_name: str
    tags: list[str] = field(default_factory=list)
    priority: int = 3  # 0=P0 (critical) through 3=P3 (low)
    description: str = ""
    parameters: list[dict[str, Any]] | None = None
    retry_count: int = 0
    timeout: float = 300.0

    def __hash__(self) -> int:
        return hash((self.file_path, self.name))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TestCase):
            return NotImplemented
        return self.file_path == other.file_path and self.name == other.name


@dataclass
class TestResult:
    test_case: TestCase
    status: Literal["passed", "failed", "skipped", "error"]
    start_time: datetime
    end_time: datetime
    duration: float
    error: Exception | None = None
    error_traceback: str | None = None
    screenshots: list[Path] = field(default_factory=list)
    video_path: Path | None = None
    log_path: Path | None = None
    artifacts: list[Path] = field(default_factory=list)
    steps: list[TestStep] = field(default_factory=list)
    retry_attempt: int = 0


@dataclass
class EnvironmentInfo:
    os: str
    python_version: str
    platform_version: str
    browser_type: str
    browser_version: str | None
    viewport: tuple[int, int]
    autoplat_version: str

    @classmethod
    def capture(cls, browser_type: str = "chromium", viewport: tuple[int, int] = (1280, 720)) -> EnvironmentInfo:
        import sys

        from ui_autoplat import __version__

        return cls(
            os=platform.system(),
            python_version=sys.version.split()[0],
            platform_version=platform.version(),
            browser_type=browser_type,
            browser_version=None,
            viewport=viewport,
            autoplat_version=__version__,
        )


@dataclass
class TestRunSummary:
    total: int
    passed: int
    failed: int
    skipped: int
    error: int
    duration: float
    pass_rate: float

    @classmethod
    def from_results(cls, results: list[TestResult]) -> TestRunSummary:
        total = len(results)
        if total == 0:
            return cls(total=0, passed=0, failed=0, skipped=0, error=0, duration=0.0, pass_rate=100.0)
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        error = sum(1 for r in results if r.status == "error")
        duration = sum(r.duration for r in results)
        pass_rate = (passed / total) * 100
        return cls(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            error=error,
            duration=duration,
            pass_rate=round(pass_rate, 1),
        )


@dataclass
class TestRun:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    environment: EnvironmentInfo | None = None
    config: dict[str, Any] | None = None
    results: list[TestResult] = field(default_factory=list)

    @property
    def summary(self) -> TestRunSummary:
        return TestRunSummary.from_results(self.results)

    @property
    def has_failures(self) -> bool:
        return any(r.status in ("failed", "error") for r in self.results)


@dataclass
class TestSuite:
    name: str
    file_path: Path
    tests: list[TestCase] = field(default_factory=list)
