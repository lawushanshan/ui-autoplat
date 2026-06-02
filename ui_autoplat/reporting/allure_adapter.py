from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ui_autoplat.config.settings import OutputConfig
from ui_autoplat.core.models import TestResult, TestRun


def _escape(string: str) -> str:
    return string.replace("\\", "\\\\").replace('"', '\\"')


class AllureAdapter:
    def __init__(self, output_config: OutputConfig) -> None:
        self._output_dir = output_config.dir / "allure-results"

    def generate(self, run: TestRun) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)

        for result in run.results:
            self._write_result(result)

        self._write_container(run)
        return self._output_dir

    def _write_result(self, result: TestResult) -> None:
        allure_result = {
            "uuid": str(uuid.uuid4()),
            "historyId": result.test_case.name,
            "fullName": f"{result.test_case.file_path}:{result.test_case.name}",
            "name": result.test_case.name,
            "labels": [
                {"name": "suite", "value": result.test_case.suite_name},
                {"name": "testMethod", "value": result.test_case.name},
                {"name": "package", "value": str(result.test_case.file_path)},
            ],
            "start": int(result.start_time.timestamp() * 1000),
            "stop": int(result.end_time.timestamp() * 1000),
        }

        if result.test_case.tags:
            for tag in result.test_case.tags:
                allure_result["labels"].append({"name": "tag", "value": tag})

        allure_result["labels"].append({"name": "severity", "value": self._priority_to_severity(result.test_case.priority)})

        allure_result["labels"].append({"name": "language", "value": "python"})

        if result.status == "passed":
            allure_result["status"] = "passed"
            allure_result["statusDetails"] = {"message": ""}
        elif result.status == "skipped":
            allure_result["status"] = "skipped"
            allure_result["statusDetails"] = {"message": "Test was skipped"}
        else:
            allure_result["status"] = "broken" if result.status == "error" else "failed"
            allure_result["statusDetails"] = {
                "message": str(result.error) if result.error else "Test failed",
                "trace": result.error_traceback or "",
            }

        if result.test_case.description:
            allure_result["description"] = result.test_case.description
            allure_result["descriptionHtml"] = f"<p>{_escape(result.test_case.description)}</p>"

        if result.screenshots:
            for screenshot_path in result.screenshots:
                self._write_attachment(screenshot_path)

        filepath = self._output_dir / f"{uuid.uuid4()}-result.json"
        filepath.write_text(json.dumps(allure_result, indent=2), encoding="utf-8")

    def _write_container(self, run: TestRun) -> None:
        children = []
        for _ in run.results:
            children.append(str(uuid.uuid4()))

        container = {
            "uuid": str(uuid.uuid4()),
            "name": f"Test Run {run.id}",
            "children": children,
            "start": int(run.timestamp.timestamp() * 1000),
            "stop": int(datetime.now().timestamp() * 1000),
        }

        filepath = self._output_dir / f"{uuid.uuid4()}-container.json"
        filepath.write_text(json.dumps(container, indent=2), encoding="utf-8")

    def _write_attachment(self, source_path: Path) -> Path:
        target = self._output_dir / f"{uuid.uuid4()}-attachment{source_path.suffix}"
        if source_path.exists():
            import shutil

            shutil.copy2(source_path, target)
        return target

    @staticmethod
    def _priority_to_severity(priority: int) -> str:
        mapping = {0: "blocker", 1: "critical", 2: "normal", 3: "minor"}
        return mapping.get(priority, "normal")
