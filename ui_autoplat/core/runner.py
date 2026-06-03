from __future__ import annotations

import subprocess
import sys
import shutil
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ui_autoplat.browser.manager import BrowserManager
from ui_autoplat.config.settings import Settings
from ui_autoplat.core.context import TestContext
from ui_autoplat.core.exceptions import TestExecutionError
from ui_autoplat.core.lifecycle import FixtureManager
from ui_autoplat.core.models import (
    EnvironmentInfo,
    TestCase,
    TestResult,
    TestRun,
    TestSuite,
)
from ui_autoplat.reporting.collector import TestResultCollector
from ui_autoplat.reporting.console_reporter import ConsoleReporter
from ui_autoplat.reporting.artifact_extractor import extract_png_screenshots_from_file
from ui_autoplat.utils.logger import get_logger

log = get_logger(__name__)


class TestRunner:
    def __init__(
        self,
        config: Settings,
        collector: TestResultCollector | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        self._config = config
        self._collector = collector or TestResultCollector(config.output)
        self._console = ConsoleReporter()
        self._fixture_mgr = FixtureManager()
        self._context = TestContext(config=config)
        self._browser_mgr = BrowserManager(config.browser, output_dir=config.output.dir)
        self._results: list[TestResult] = []
        self._should_cancel = should_cancel or (lambda: False)

    @property
    def results(self) -> list[TestResult]:
        return self._results

    def run(self, suites: list[TestSuite]) -> TestRun:
        self._reset_run_state()
        all_tests = [tc for suite in suites for tc in suite.tests]
        total = len(all_tests)

        self._console.run_started(total)

        if not all_tests:
            self._console.run_finished([])
            return TestRun(environment=EnvironmentInfo.capture(self._config.browser.browser_type))

        if self._config.execution.mode == "subprocess":
            if self._config.execution.max_parallel > 1 and not self._config.execution.stop_on_first_failure:
                self._run_subprocess_parallel(all_tests)
            else:
                self._run_subprocess_sequential(all_tests)
        else:
            self._browser_mgr.configure()
            self._fixture_mgr.run_setup("suite", self._context)
            try:
                for index, test in enumerate(all_tests):
                    if self._should_cancel():
                        self._record_cancelled_results(all_tests[index:])
                        break

                    result = self._execute_in_process(test)
                    self._record_result(result)

                    if result.status in ("failed", "error") and self._config.execution.stop_on_first_failure:
                        break
            finally:
                self._fixture_mgr.run_teardown("suite", self._context)
                self._browser_mgr.close()

        self._console.run_finished(self._results)

        run = TestRun(
            environment=EnvironmentInfo.capture(
                self._config.browser.browser_type,
                (self._config.browser.viewport.get("width", 1280), self._config.browser.viewport.get("height", 720)),
            ),
            results=self._results,
        )
        self._collector.record_run(run)
        return run

    def _reset_run_state(self) -> None:
        self._results = []
        self._collector.clear()

    def _record_result(self, result: TestResult) -> None:
        self._results.append(result)
        self._collector.add_result(result)
        self._console.test_finished(result)

    def _run_subprocess_sequential(self, tests: list[TestCase]) -> None:
        for index, test in enumerate(tests):
            if self._should_cancel():
                self._record_cancelled_results(tests[index:])
                break

            result = self._execute_subprocess(test)
            self._record_result(result)

            if result.status in ("failed", "error") and self._config.execution.stop_on_first_failure:
                log.info("Stopping on first failure: %s", test.name)
                break

    def _run_subprocess_parallel(self, tests: list[TestCase]) -> None:
        if self._should_cancel():
            self._record_cancelled_results(tests)
            return

        max_workers = min(self._config.execution.max_parallel, len(tests))
        ordered_results: list[TestResult | None] = [None] * len(tests)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(self._execute_subprocess, test): index
                for index, test in enumerate(tests)
            }
            for future in as_completed(future_to_index):
                ordered_results[future_to_index[future]] = future.result()

        for result in ordered_results:
            if result is not None:
                self._record_result(result)

    def run_single(self, test: TestCase) -> TestResult:
        self._console.test_started(test)

        if self._should_cancel():
            result = self._skipped_result_with_reason(test, "Cancelled by request")
            self._results.append(result)
            self._collector.add_result(result)
            self._console.test_finished(result)
            return result

        if self._config.execution.mode == "subprocess":
            result = self._execute_subprocess(test)
        else:
            result = self._execute_in_process(test)

        self._results.append(result)
        self._collector.add_result(result)
        self._console.test_finished(result)
        return result

    def _execute_subprocess(self, test: TestCase) -> TestResult:
        if test.skip_reason:
            return self._skipped_result(test)

        last_result: TestResult | None = None
        for attempt in range(self._config.execution.retries + 1):
            last_result = self._execute_subprocess_once(test, retry_attempt=attempt)
            if last_result.status == "passed":
                return last_result
        return last_result  # type: ignore[return-value]

    def _execute_subprocess_once(self, test: TestCase, retry_attempt: int = 0) -> TestResult:
        start_time = datetime.now()

        if test.parameters:
            end_time = datetime.now()
            return TestResult(
                test_case=test,
                status="error",
                start_time=start_time,
                end_time=end_time,
                duration=(end_time - start_time).total_seconds(),
                error=TestExecutionError("Data-driven tests require in-process execution mode"),
                retry_attempt=retry_attempt,
            )

        cmd = [
            sys.executable,
            "-m",
            "robocorp.tasks",
            "run",
            test.file_path.name,
            "-t",
            test.function.__name__,
        ]

        env = {
            **self._build_env(),
            "AUTOPLAT_OUTPUT_DIR": str(self._config.output.dir),
        }

        try:
            proc_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._config.execution.timeout_per_test,
                env=env,
                cwd=str(test.file_path.parent.resolve()),
            )
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if proc_result.returncode == 0:
                return TestResult(
                    test_case=test,
                    status="passed",
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    retry_attempt=retry_attempt,
                )
            else:
                combined_output = _combine_process_output(proc_result.stdout, proc_result.stderr)
                error_message = _extract_failure_summary(combined_output) or "Task failed"
                result = TestResult(
                    test_case=test,
                    status="failed",
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    error=TestExecutionError(error_message),
                    error_traceback=combined_output,
                    retry_attempt=retry_attempt,
                )
                self._write_subprocess_output_artifacts(
                    result,
                    stdout=proc_result.stdout,
                    stderr=proc_result.stderr,
                )
                self._attach_subprocess_artifacts(result)
                return result

        except subprocess.TimeoutExpired as exc:
            end_time = datetime.now()
            result = TestResult(
                test_case=test,
                status="error",
                start_time=start_time,
                end_time=end_time,
                duration=(end_time - start_time).total_seconds(),
                error=TestExecutionError(f"Test timed out after {self._config.execution.timeout_per_test}s"),
                retry_attempt=retry_attempt,
            )
            self._write_subprocess_output_artifacts(
                result,
                stdout=_decode_process_output(exc.stdout),
                stderr=_decode_process_output(exc.stderr),
            )
            self._attach_subprocess_artifacts(result)
            return result
        except Exception as e:
            end_time = datetime.now()
            result = TestResult(
                test_case=test,
                status="error",
                start_time=start_time,
                end_time=end_time,
                duration=(end_time - start_time).total_seconds(),
                error=e,
                error_traceback=str(e),
                retry_attempt=retry_attempt,
            )
            self._attach_subprocess_artifacts(result)
            return result

    def _execute_in_process(self, test: TestCase) -> TestResult:
        if test.skip_reason:
            return self._skipped_result(test)

        start_time = datetime.now()

        retries = self._config.execution.retries
        last_result: TestResult | None = None

        for attempt in range(retries + 1):
            self._context.current_test = test
            self._context.test_params = test.parameters[0] if test.parameters else None
            self._fixture_mgr.run_setup("task", self._context)

            try:
                if test.parameters:
                    params = test.parameters[0]
                    if isinstance(params, dict):
                        test.function(params)
                    else:
                        test.function(params)
                else:
                    test.function()
                end_time = datetime.now()
                return TestResult(
                    test_case=test,
                    status="passed",
                    start_time=start_time,
                    end_time=end_time,
                    duration=(end_time - start_time).total_seconds(),
                    retry_attempt=attempt,
                )
            except Exception as e:
                end_time = datetime.now()
                last_result = TestResult(
                    test_case=test,
                    status="failed",
                    start_time=start_time,
                    end_time=end_time,
                    duration=(end_time - start_time).total_seconds(),
                    error=e,
                    error_traceback=str(e),
                    retry_attempt=attempt,
                )
                self._attach_in_process_artifacts(last_result)
            finally:
                self._fixture_mgr.run_teardown("task", self._context)
                self._context.current_test = None
                self._context.test_params = None

        return last_result  # type: ignore[return-value]

    def _skipped_result(self, test: TestCase) -> TestResult:
        return self._skipped_result_with_reason(test, test.skip_reason or "Skipped")

    def _skipped_result_with_reason(self, test: TestCase, reason: str) -> TestResult:
        now = datetime.now()
        return TestResult(
            test_case=test,
            status="skipped",
            start_time=now,
            end_time=now,
            duration=0.0,
            error=TestExecutionError(reason),
            error_traceback=reason,
        )

    def _record_cancelled_results(self, tests: list[TestCase]) -> None:
        for test in tests:
            self._record_result(self._skipped_result_with_reason(test, "Cancelled by request"))

    def _attach_in_process_artifacts(self, result: TestResult) -> None:
        if result.status not in ("failed", "error"):
            return
        if self._config.browser.screenshot == "off":
            return
        from ui_autoplat.browser.screenshots import capture_on_failure

        screenshot = capture_on_failure(
            test_name=result.test_case.name,
            error=result.error,
            output_dir=self._config.output.dir / "screenshots",
        )
        if screenshot is not None and screenshot.exists():
            result.screenshots.append(screenshot)
            result.artifacts.append(screenshot)

    def _write_subprocess_output_artifacts(
        self,
        result: TestResult,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        artifact_dir = self._artifact_dir(result)
        outputs = {
            "stdout.log": stdout,
            "stderr.log": stderr,
        }
        for filename, content in outputs.items():
            if not content:
                continue
            artifact_dir.mkdir(parents=True, exist_ok=True)
            path = artifact_dir / filename
            path.write_text(content, encoding="utf-8", errors="replace")
            if path not in result.artifacts:
                result.artifacts.append(path)

    def _attach_subprocess_artifacts(self, result: TestResult) -> None:
        artifact_dir = self._artifact_dir(result)
        source_dirs = [result.test_case.file_path.parent / "output", self._config.output.dir]
        artifact_patterns = ("log.html", "output.robolog", "stderr.log", "stdout.log")

        for source_dir in source_dirs:
            if not source_dir.exists() or source_dir.resolve() == artifact_dir.resolve():
                continue
            for pattern in artifact_patterns:
                for source in source_dir.rglob(pattern):
                    target = artifact_dir / source.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(source, target)
                    except OSError:
                        continue
                    if target not in result.artifacts:
                        result.artifacts.append(target)
                    if source.name == "log.html":
                        result.log_path = target
                    if source.name == "output.robolog":
                        self._extract_screenshots_from_robolog(result, target)

    def _extract_screenshots_from_robolog(self, result: TestResult, robolog_path: Path) -> None:
        screenshot_dir = self._config.output.dir / "screenshots"
        prefix = f"{result.test_case.suite_name}_{result.test_case.name}"
        screenshots = extract_png_screenshots_from_file(
            robolog_path,
            output_dir=screenshot_dir,
            prefix=prefix,
        )
        for screenshot in screenshots:
            if screenshot not in result.screenshots:
                result.screenshots.append(screenshot)
            if screenshot not in result.artifacts:
                result.artifacts.append(screenshot)

    def _artifact_dir(self, result: TestResult) -> Path:
        return self._config.output.dir / "artifacts" / result.test_case.suite_name / result.test_case.name

    def _build_env(self) -> dict[str, str]:
        import os

        env = os.environ.copy()
        env["AUTOPLAT_BROWSER_TYPE"] = self._config.browser.browser_type
        env["AUTOPLAT_BROWSER_HEADLESS"] = str(self._config.browser.headless).lower()
        env["AUTOPLAT_BROWSER_SCREENSHOT"] = self._config.browser.screenshot
        env["AUTOPLAT_BROWSER_SLOWMO"] = str(self._config.browser.slowmo)
        return env


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_WARNING_HEADER_RE = re.compile(r"^.+:\d+:\s+Warning:\s+")
_TRACEBACK_HEADER_RE = re.compile(r"^=+\s+Full Traceback", re.IGNORECASE)
_NOISE_PATTERNS = (
    "Usage of the native system certificate stores",
    "_inject_truststore()",
)


def _combine_process_output(stdout: str | None, stderr: str | None) -> str:
    parts = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(stderr)
    return "\n".join(parts)


def _decode_process_output(value: str | bytes | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _extract_failure_summary(output: str) -> str | None:
    clean_lines = _clean_process_output_lines(output)
    if not clean_lines:
        return None

    traceback_summary = _extract_traceback_exception(clean_lines)
    if traceback_summary:
        return traceback_summary

    for line in clean_lines:
        if _looks_like_failure_line(line):
            return line

    return clean_lines[0]


def _clean_process_output_lines(output: str) -> list[str]:
    lines = []
    for raw_line in output.splitlines():
        line = _ANSI_ESCAPE_RE.sub("", raw_line).strip()
        if not line:
            continue
        if any(pattern in line for pattern in _NOISE_PATTERNS):
            continue
        if _WARNING_HEADER_RE.match(line):
            continue
        if set(line) <= {"=", "-"}:
            continue
        if line.startswith("Log (html):"):
            continue
        if line.startswith("Collecting task "):
            continue
        if line.startswith("Running: "):
            continue
        if line.endswith(" status: FAIL"):
            continue
        lines.append(line)
    return lines


def _extract_traceback_exception(lines: list[str]) -> str | None:
    in_traceback = False
    for line in reversed(lines):
        if _TRACEBACK_HEADER_RE.match(line):
            break
        if line.startswith("Traceback "):
            in_traceback = True
            break
        if not in_traceback and _looks_like_exception_line(line):
            return line
    return None


def _looks_like_failure_line(line: str) -> bool:
    if _looks_like_exception_line(line):
        return True
    return any(marker in line for marker in ("AssertionError", "Timeout", "Error:", "failed", "exceeded"))


def _looks_like_exception_line(line: str) -> bool:
    if line.startswith(("File ", "Call log:", "- waiting for ")):
        return False
    if ":" not in line:
        return False
    left, _right = line.split(":", 1)
    return left.endswith(("Error", "Exception")) or "." in left and left.rsplit(".", 1)[-1].endswith("Error")
