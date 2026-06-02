from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ui_autoplat.config.settings import OutputConfig
from ui_autoplat.core.models import TestResult, TestRun


class TestResultCollector:
    def __init__(self, output_config: OutputConfig) -> None:
        self._results: list[TestResult] = []
        self._output_dir = output_config.dir
        self._keep_reports = output_config.keep_reports

    def add_result(self, result: TestResult) -> None:
        self._results.append(result)

    def get_all_results(self) -> list[TestResult]:
        return list(self._results)

    def clear(self) -> None:
        self._results.clear()

    def record_run(self, run: TestRun) -> None:
        self._ensure_output_dir()
        from ui_autoplat.reporting.history import HistoryStore

        history = HistoryStore(db_path=self._output_dir / "history.db")
        history.record_run(run)
        history.close()

    def _ensure_output_dir(self) -> None:
        reports_dir = self._output_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
