from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from ui_autoplat.config.settings import OutputConfig
from ui_autoplat.core.models import TestResult, TestRun


class JUnitReportGenerator:
    def __init__(self, output_config: OutputConfig) -> None:
        self._output_dir = output_config.dir / "reports"

    def generate(self, run: TestRun) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)

        summary = run.summary
        suite = ET.Element(
            "testsuite",
            {
                "name": "ui-autoplat",
                "tests": str(summary.total),
                "failures": str(summary.failed),
                "errors": str(summary.error),
                "skipped": str(summary.skipped),
                "time": f"{summary.duration:.3f}",
                "timestamp": run.timestamp.isoformat(),
            },
        )

        if run.environment:
            properties = ET.SubElement(suite, "properties")
            for name, value in {
                "os": run.environment.os,
                "python_version": run.environment.python_version,
                "browser_type": run.environment.browser_type,
                "viewport": f"{run.environment.viewport[0]}x{run.environment.viewport[1]}",
                "autoplat_version": run.environment.autoplat_version,
            }.items():
                ET.SubElement(properties, "property", {"name": name, "value": str(value)})

        for result in run.results:
            suite.append(self._testcase_element(result))

        tree = ET.ElementTree(suite)
        ET.indent(tree, space="  ")

        report_path = self._output_dir / "junit.xml"
        tree.write(report_path, encoding="utf-8", xml_declaration=True)
        return report_path

    def _testcase_element(self, result: TestResult) -> ET.Element:
        testcase = ET.Element(
            "testcase",
            {
                "classname": result.test_case.suite_name,
                "name": result.test_case.name,
                "file": str(result.test_case.file_path),
                "time": f"{result.duration:.3f}",
            },
        )

        if result.status == "failed":
            failure = ET.SubElement(
                testcase,
                "failure",
                {
                    "message": str(result.error) if result.error else "Test failed",
                    "type": type(result.error).__name__ if result.error else "AssertionError",
                },
            )
            failure.text = result.error_traceback or str(result.error) if result.error else ""
        elif result.status == "error":
            error = ET.SubElement(
                testcase,
                "error",
                {
                    "message": str(result.error) if result.error else "Test error",
                    "type": type(result.error).__name__ if result.error else "Exception",
                },
            )
            error.text = result.error_traceback or str(result.error) if result.error else ""
        elif result.status == "skipped":
            ET.SubElement(testcase, "skipped")

        system_out_lines = []
        if result.screenshots:
            system_out_lines.append("Screenshots:")
            system_out_lines.extend(str(path) for path in result.screenshots)
        if result.log_path:
            system_out_lines.append(f"Log: {result.log_path}")
        if result.video_path:
            system_out_lines.append(f"Video: {result.video_path}")
        if result.artifacts:
            system_out_lines.append("Artifacts:")
            system_out_lines.extend(str(path) for path in result.artifacts)
        if system_out_lines:
            system_out = ET.SubElement(testcase, "system-out")
            system_out.text = "\n".join(system_out_lines)

        return testcase
