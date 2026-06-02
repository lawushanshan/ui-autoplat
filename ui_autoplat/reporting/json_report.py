from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ui_autoplat.config.settings import OutputConfig
from ui_autoplat.core.models import TestResult, TestRun


class JSONReportGenerator:
    def __init__(self, output_config: OutputConfig) -> None:
        self._output_dir = output_config.dir / "reports"

    def generate(self, run: TestRun) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)

        def _serialize_result(r: TestResult) -> dict:
            return {
                "name": r.test_case.name,
                "suite": r.test_case.suite_name,
                "file": str(r.test_case.file_path),
                "tags": r.test_case.tags,
                "priority": r.test_case.priority,
                "case_id": r.test_case.case_id,
                "case_name": r.test_case.case_name,
                "parameters": r.test_case.parameters[0] if r.test_case.parameters else None,
                "skip_reason": r.test_case.skip_reason,
                "status": r.status,
                "duration": round(r.duration, 2),
                "error": str(r.error) if r.error else None,
                "traceback": r.error_traceback,
                "screenshots": [str(s) for s in r.screenshots],
                "video": str(r.video_path) if r.video_path else None,
                "log": str(r.log_path) if r.log_path else None,
                "artifacts": [str(a) for a in r.artifacts],
                "retry_attempt": r.retry_attempt,
            }

        data = {
            "run_id": run.id,
            "timestamp": run.timestamp.isoformat(),
            "environment": {
                "os": run.environment.os if run.environment else None,
                "python_version": run.environment.python_version if run.environment else None,
                "browser_type": run.environment.browser_type if run.environment else None,
                "viewport": list(run.environment.viewport) if run.environment else None,
                "autoplat_version": run.environment.autoplat_version if run.environment else None,
            },
            "summary": {
                "total": run.summary.total,
                "passed": run.summary.passed,
                "failed": run.summary.failed,
                "skipped": run.summary.skipped,
                "error": run.summary.error,
                "pass_rate": run.summary.pass_rate,
                "duration": round(run.summary.duration, 2),
            },
            "results": [_serialize_result(r) for r in run.results],
        }

        report_path = self._output_dir / "results.json"
        report_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return report_path
