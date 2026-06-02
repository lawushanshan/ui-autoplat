from __future__ import annotations

import subprocess
import sys
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

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
    ) -> None:
        self._config = config
        self._collector = collector or TestResultCollector(config.output)
        self._console = ConsoleReporter()
        self._fixture_mgr = FixtureManager()
        self._context = TestContext(config=config)
        self._browser_mgr = BrowserManager(config.browser, output_dir=config.output.dir)
        self._results: list[TestResult] = []

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
                for test in all_tests:
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
        for test in tests:
            result = self._execute_subprocess(test)
            self._record_result(result)

            if result.status in ("failed", "error") and self._config.execution.stop_on_first_failure:
                log.info("Stopping on first failure: %s", test.name)
                break

    def _run_subprocess_parallel(self, tests: list[TestCase]) -> None:
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
                result = TestResult(
                    test_case=test,
                    status="failed",
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    error=TestExecutionError(proc_result.stderr.strip() or "Task failed"),
                    error_traceback=proc_result.stderr,
                    retry_attempt=retry_attempt,
                )
                self._attach_subprocess_artifacts(result)
                return result

        except subprocess.TimeoutExpired:
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
        now = datetime.now()
        return TestResult(
            test_case=test,
            status="skipped",
            start_time=now,
            end_time=now,
            duration=0.0,
            error=TestExecutionError(test.skip_reason or "Skipped"),
            error_traceback=test.skip_reason,
        )

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

    def _attach_subprocess_artifacts(self, result: TestResult) -> None:
        artifact_dir = self._config.output.dir / "artifacts" / result.test_case.suite_name / result.test_case.name
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

    def _build_env(self) -> dict[str, str]:
        import os

        env = os.environ.copy()
        env["AUTOPLAT_BROWSER_TYPE"] = self._config.browser.browser_type
        env["AUTOPLAT_BROWSER_HEADLESS"] = str(self._config.browser.headless).lower()
        env["AUTOPLAT_BROWSER_SCREENSHOT"] = self._config.browser.screenshot
        env["AUTOPLAT_BROWSER_SLOWMO"] = str(self._config.browser.slowmo)
        return env
