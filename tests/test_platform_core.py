from __future__ import annotations

from datetime import datetime
from pathlib import Path
import time
import sys
import types
import subprocess
from xml.etree import ElementTree as ET

from ui_autoplat.actions import endpoints
from ui_autoplat.actions.server import APIRequestHandler
from ui_autoplat.assertions.web_assertions import expect_text, expect_url_contains, expect_visible
from ui_autoplat.browser.manager import BrowserManager
from ui_autoplat.browser.page_objects import BasePage
from ui_autoplat.config.settings import Settings
from ui_autoplat.core.exceptions import DataDrivenError, RegistryError
from ui_autoplat.core.models import EnvironmentInfo, TestResult as AutoplatTestResult, TestRun as AutoplatTestRun
from ui_autoplat.core.registry import discover_tests
from ui_autoplat.core.runner import TestRunner as AutoplatTestRunner
from ui_autoplat.reporting.html_report import HTMLReportGenerator
from ui_autoplat.reporting.history import HistoryStore
from ui_autoplat.reporting.junit_report import JUnitReportGenerator
from ui_autoplat.reporting.json_report import JSONReportGenerator
from ui_autoplat.reporting.console_reporter import ConsoleReporter
from ui_autoplat.utils.data_driven import load_csv, load_json

MINIMAL_PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _write_task_file(path: Path) -> None:
    path.write_text(
        """
from robocorp.tasks import task


@task
def test_smoke():
    \"\"\"Smoke task. Tags: smoke, P0\"\"\"
    assert True


@task
def test_regression():
    \"\"\"Regression task. Tags: regression, P1\"\"\"
    assert True
""",
        encoding="utf-8",
    )


def test_browser_type_accepts_scaffold_alias() -> None:
    settings = Settings.model_validate({"browser": {"type": "firefox"}})

    assert settings.browser.browser_type == "firefox"


def test_browser_manager_close_supports_context_close(monkeypatch) -> None:
    closed = []

    class FakeContext:
        def close(self):
            closed.append(True)

    fake_browser = types.SimpleNamespace(context=lambda: FakeContext())
    fake_robocorp = types.SimpleNamespace(browser=fake_browser)
    monkeypatch.setitem(sys.modules, "robocorp", fake_robocorp)

    manager = BrowserManager(Settings().browser)
    manager.close()

    assert closed == [True]


def test_browser_manager_applies_context_configuration(monkeypatch, tmp_path: Path) -> None:
    configure_calls = []
    context_calls = []

    fake_browser = types.SimpleNamespace(
        configure=lambda **kwargs: configure_calls.append(kwargs),
        configure_context=lambda **kwargs: context_calls.append(kwargs),
    )
    fake_robocorp = types.SimpleNamespace(browser=fake_browser)
    monkeypatch.setitem(sys.modules, "robocorp", fake_robocorp)

    settings = Settings.model_validate(
        {
            "browser": {
                "browser_type": "chromium",
                "headless": True,
                "screenshot": "only-on-failure",
                "slowmo": 50,
                "viewport": {"width": 1440, "height": 900},
                "locale": "zh-CN",
                "timezone": "Asia/Shanghai",
                "record_video": True,
            }
        }
    )
    manager = BrowserManager(settings.browser, output_dir=tmp_path / "output")

    manager.configure()

    assert configure_calls == [
        {
            "browser_engine": "chromium",
            "headless": True,
            "screenshot": "only-on-failure",
            "slowmo": 50,
        }
    ]
    assert context_calls == [
        {
            "viewport": {"width": 1440, "height": 900},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
            "record_video_dir": str(tmp_path / "output" / "videos"),
        }
    ]


def test_settings_defaults_do_not_share_mutable_instances() -> None:
    first = Settings()
    second = Settings()

    first.browser.viewport["width"] = 1440
    first.discovery.paths.append(Path("./other-tests"))
    first.discovery.tags.append("smoke")

    assert second.browser.viewport["width"] == 1280
    assert second.discovery.paths == [Path("./tests")]
    assert second.discovery.tags == []


def test_base_page_exposes_chainable_common_actions(monkeypatch) -> None:
    calls = []

    class FakeLocator:
        def __init__(self, selector: str) -> None:
            self.selector = selector

        def wait_for(self, **kwargs):
            calls.append(("wait_for", self.selector, kwargs))

        def fill(self, value: str, **kwargs):
            calls.append(("fill", self.selector, value, kwargs))

        def click(self, **kwargs):
            calls.append(("click", self.selector, kwargs))

        def text_content(self):
            calls.append(("text_content", self.selector))
            return "Dashboard"

    class FakePage:
        url = "https://example.test/login"

        def locator(self, selector: str):
            calls.append(("locator", selector))
            return FakeLocator(selector)

    fake_page = FakePage()
    fake_browser = types.SimpleNamespace(
        goto=lambda url: calls.append(("goto", url)),
        page=lambda: fake_page,
    )
    monkeypatch.setitem(sys.modules, "robocorp", types.SimpleNamespace(browser=fake_browser))

    class LoginPage(BasePage):
        url = "https://example.test/login"

        def wait_for_ready(self) -> None:
            self.wait_visible("#username")

    page = LoginPage()
    returned = page.goto().fill("#username", "admin").click("button[type=submit]")

    assert returned is page
    assert page.text("h1") == "Dashboard"
    assert ("goto", "https://example.test/login") in calls
    assert ("fill", "#username", "admin", {}) in calls
    assert ("click", "button[type=submit]", {}) in calls


def test_web_expectations_include_selector_and_url_in_failures() -> None:
    class FakeLocator:
        def wait_for(self, **kwargs):
            return None

        def is_visible(self):
            return False

    class FakePage:
        url = "https://example.test/login"

        def locator(self, selector: str):
            return FakeLocator()

    try:
        expect_visible("#dashboard", page=FakePage())
    except AssertionError as exc:
        message = str(exc)
    else:
        raise AssertionError("expect_visible should fail")

    assert "#dashboard" in message
    assert "https://example.test/login" in message


def test_web_expectation_aliases_cover_text_and_url() -> None:
    class FakeLocator:
        def wait_for(self, **kwargs):
            return None

        def text_content(self):
            return "Welcome"

    class FakePage:
        url = "https://example.test/dashboard"

        def locator(self, selector: str):
            return FakeLocator()

        def wait_for_url(self, pattern: str, timeout: float):
            return None

    page = FakePage()

    expect_text("h1", "Welcome", page=page)
    expect_url_contains("dashboard", page=page)


def test_discover_supports_and_and_or_tag_matching(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)

    and_suites = discover_tests([tmp_path], tags=["smoke", "regression"])
    or_suites = discover_tests([tmp_path], tags=["smoke", "regression"], match_any_tag=True)

    assert [tc.name for suite in and_suites for tc in suite.tests] == []
    assert {tc.name for suite in or_suites for tc in suite.tests} == {"test_smoke", "test_regression"}


def test_discover_imports_same_named_task_files_as_distinct_modules(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    _write_task_file(first_dir / "same_task.py")
    _write_task_file(second_dir / "same_task.py")

    suites = discover_tests([tmp_path])
    tests = [tc for suite in suites for tc in suite.tests if tc.name == "test_smoke"]

    assert len(tests) == 2
    assert len({tc.file_path.parent.name for tc in tests}) == 2
    assert len({tc.function.__module__ for tc in tests}) == 2


def test_runner_only_executes_filtered_suite_tests(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    suites[0].tests = [tc for tc in suites[0].tests if tc.name == "test_smoke"]

    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    run = AutoplatTestRunner(settings).run(suites)

    assert [r.test_case.name for r in run.results] == ["test_smoke"]
    assert run.summary.passed == 1


def test_runner_run_resets_previous_results(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    runner = AutoplatTestRunner(settings)

    first = runner.run(suites)
    second = runner.run(suites)

    assert len(first.results) == 2
    assert len(second.results) == 2
    assert len(runner.results) == 2


def test_in_process_runner_sets_and_clears_current_context(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    suites[0].tests = [tc for tc in suites[0].tests if tc.name == "test_smoke"]
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    runner = AutoplatTestRunner(settings)
    seen_context = []

    runner._fixture_mgr.register_task_setup(
        lambda: seen_context.append(runner._context.current_test.name)
    )

    run = runner.run(suites)

    assert run.summary.passed == 1
    assert seen_context == ["test_smoke"]
    assert runner._context.current_test is None
    assert runner._context.test_params is None


def test_in_process_runner_configures_and_closes_browser_manager(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    suites[0].tests = [tc for tc in suites[0].tests if tc.name == "test_smoke"]
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    runner = AutoplatTestRunner(settings)
    calls = []

    class FakeBrowserManager:
        def configure(self):
            calls.append("configure")

        def close(self):
            calls.append("close")

    runner._browser_mgr = FakeBrowserManager()

    run = runner.run(suites)

    assert run.summary.passed == 1
    assert calls == ["configure", "close"]


def test_in_process_runner_closes_browser_manager_after_failure(tmp_path: Path) -> None:
    task_file = tmp_path / "failing_task.py"
    task_file.write_text(
        """
from robocorp.tasks import task


@task
def test_fails():
    raise AssertionError("boom")
""",
        encoding="utf-8",
    )
    suites = discover_tests([tmp_path])
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "browser": {"screenshot": "off"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    runner = AutoplatTestRunner(settings)
    calls = []

    class FakeBrowserManager:
        def configure(self):
            calls.append("configure")

        def close(self):
            calls.append("close")

    runner._browser_mgr = FakeBrowserManager()

    run = runner.run(suites)

    assert run.summary.failed == 1
    assert calls == ["configure", "close"]


def test_in_process_runner_exposes_data_driven_params_in_context(tmp_path: Path) -> None:
    data_file = tmp_path / "users.json"
    data_file.write_text('[{"name": "alice"}]', encoding="utf-8")
    task_file = tmp_path / "data_task.py"
    task_file.write_text(
        f"""
from pathlib import Path

from robocorp.tasks import task
from ui_autoplat.utils.data_driven import data_driven


@data_driven(Path(r"{data_file}"))
@task
def test_user(row):
    assert row["name"] == "alice"
""",
        encoding="utf-8",
    )
    suites = discover_tests([tmp_path])
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    runner = AutoplatTestRunner(settings)
    seen_params = []

    runner._fixture_mgr.register_task_setup(
        lambda: seen_params.append(runner._context.test_params)
    )

    run = runner.run(suites)

    assert run.summary.passed == 1
    assert seen_params == [{"name": "alice"}]
    assert runner._context.test_params is None


def test_parallel_subprocess_results_keep_discovery_order(tmp_path: Path, monkeypatch) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    settings = Settings.model_validate(
        {
            "execution": {"mode": "subprocess", "max_parallel": 2},
            "output": {"dir": tmp_path / "output"},
        }
    )
    runner = AutoplatTestRunner(settings)

    def fake_execute_subprocess(test_case):
        if test_case.name == "test_smoke":
            time.sleep(0.05)
        now = datetime.now()
        return AutoplatTestResult(
            test_case=test_case,
            status="passed",
            start_time=now,
            end_time=now,
            duration=0,
        )

    monkeypatch.setattr(runner, "_execute_subprocess", fake_execute_subprocess)

    run = runner.run(suites)

    assert [result.test_case.name for result in run.results] == [
        test_case.name for suite in suites for test_case in suite.tests
    ]


def test_dynamic_route_matching_extracts_params() -> None:
    APIRequestHandler._routes.clear()
    APIRequestHandler.register("/api/runs/{run_id}", lambda run_id: {"run_id": run_id})

    matched = APIRequestHandler._match_route("GET", "/api/runs/abc123")

    assert matched is not None
    handler, params = matched
    assert params == {"run_id": "abc123"}
    assert handler(**params) == {"run_id": "abc123"}


def test_data_driven_discovery_and_in_process_execution(tmp_path: Path) -> None:
    data_file = tmp_path / "users.json"
    data_file.write_text('[{"name": "alice"}, {"name": "bob"}]', encoding="utf-8")
    task_file = tmp_path / "data_task.py"
    task_file.write_text(
        f"""
from pathlib import Path

from robocorp.tasks import task
from ui_autoplat.utils.data_driven import data_driven

seen = []


@data_driven(Path(r"{data_file}"))
@task
def test_user(row):
    \"\"\"Data task. Tags: data, P1\"\"\"
    seen.append(row["name"])
""",
        encoding="utf-8",
    )

    suites = discover_tests([tmp_path])
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output"},
        }
    )

    run = AutoplatTestRunner(settings).run(suites)

    assert [tc.name for suite in suites for tc in suite.tests] == ["test_user[1]", "test_user[2]"]
    assert run.summary.passed == 2


def test_data_driven_relative_source_resolves_from_task_file(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "users.json").write_text('[{"name": "alice"}]', encoding="utf-8")
    task_file = tmp_path / "relative_data_task.py"
    task_file.write_text(
        """
from robocorp.tasks import task
from ui_autoplat.utils.data_driven import data_driven


@data_driven("data/users.json")
@task
def test_user(row):
    assert row["name"]
""",
        encoding="utf-8",
    )

    suites = discover_tests([tmp_path])

    assert [tc.name for suite in suites for tc in suite.tests] == ["test_user[1]"]


def test_data_driven_case_metadata_and_skip_are_reported(tmp_path: Path, monkeypatch) -> None:
    data_file = tmp_path / "users.json"
    data_file.write_text(
        """
[
  {"case_id": "LOGIN-001", "case_name": "valid user", "name": "alice"},
  {"case_id": "LOGIN-002", "name": "bob", "skip": true, "skip_reason": "waiting for account"}
]
""",
        encoding="utf-8",
    )
    task_file = tmp_path / "data_task.py"
    task_file.write_text(
        f"""
from pathlib import Path

from robocorp.tasks import task
from ui_autoplat.utils.data_driven import data_driven

seen = []


@data_driven(Path(r"{data_file}"))
@task
def test_user(row):
    seen.append(row["name"])
""",
        encoding="utf-8",
    )

    suites = discover_tests([tmp_path])
    tests = [tc for suite in suites for tc in suite.tests]

    assert [tc.name for tc in tests] == ["test_user[LOGIN-001]", "test_user[LOGIN-002]"]
    assert tests[0].case_id == "LOGIN-001"
    assert tests[0].case_name == "valid user"
    assert tests[1].skip_reason == "waiting for account"

    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output", "report_format": "json"},
        }
    )
    run = AutoplatTestRunner(settings).run(suites)

    assert run.summary.total == 2
    assert run.summary.passed == 1
    assert run.summary.skipped == 1
    assert [result.status for result in run.results] == ["passed", "skipped"]

    report_path = JSONReportGenerator(settings.output).generate(run)
    report = report_path.read_text(encoding="utf-8")
    assert '"case_id": "LOGIN-001"' in report
    assert '"case_name": "valid user"' in report
    assert '"skip_reason": "waiting for account"' in report

    junit_path = JUnitReportGenerator(settings.output).generate(run)
    root = ET.parse(junit_path).getroot()
    skipped_case = root.findall("testcase")[1]
    assert skipped_case.attrib["case_id"] == "LOGIN-002"
    skipped = skipped_case.find("skipped")
    assert skipped is not None
    assert skipped.attrib["message"] == "waiting for account"

    (tmp_path / "autoplat.yaml").write_text(
        f"""
output:
  dir: {tmp_path / "output"}
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(endpoints, "_last_run", None)
    response = endpoints.get_run_results(run.id)

    assert response["results"][0]["case_id"] == "LOGIN-001"
    assert response["results"][0]["parameters"]["name"] == "alice"
    assert response["results"][1]["skip_reason"] == "waiting for account"


def test_data_driven_csv_metadata_is_supported(tmp_path: Path) -> None:
    data_file = tmp_path / "users.csv"
    data_file.write_text(
        "case_id,case_name,name,skip,skip_reason\n"
        "CSV-001,valid csv,alice,,\n"
        "CSV-002,skipped csv,bob,true,waiting for csv account\n",
        encoding="utf-8",
    )
    task_file = tmp_path / "csv_task.py"
    task_file.write_text(
        """
from robocorp.tasks import task
from ui_autoplat.utils.data_driven import data_driven


@data_driven("users.csv")
@task
def test_csv(row):
    assert row["name"]
""",
        encoding="utf-8",
    )

    suites = discover_tests([tmp_path])
    tests = [tc for suite in suites for tc in suite.tests]

    assert [tc.name for tc in tests] == ["test_csv[CSV-001]", "test_csv[CSV-002]"]
    assert tests[0].case_name == "valid csv"
    assert tests[1].skip_reason == "waiting for csv account"


def test_data_driven_invalid_json_rows_raise_clear_error(tmp_path: Path) -> None:
    data_file = tmp_path / "users.json"
    data_file.write_text('["alice"]', encoding="utf-8")

    try:
        load_json(data_file)
    except DataDrivenError as exc:
        message = str(exc)
    else:
        raise AssertionError("load_json should reject non-object rows")

    assert "row 1" in message
    assert "must be an object" in message


def test_data_driven_empty_csv_raises_clear_error(tmp_path: Path) -> None:
    data_file = tmp_path / "users.csv"
    data_file.write_text("", encoding="utf-8")

    try:
        load_csv(data_file)
    except DataDrivenError as exc:
        message = str(exc)
    else:
        raise AssertionError("load_csv should reject empty files")

    assert "no header row" in message


def test_discovery_reports_invalid_data_source_context(tmp_path: Path) -> None:
    task_file = tmp_path / "missing_data_task.py"
    task_file.write_text(
        """
from robocorp.tasks import task
from ui_autoplat.utils.data_driven import data_driven


@data_driven("missing.json")
@task
def test_missing_data(row):
    assert row
""",
        encoding="utf-8",
    )

    try:
        discover_tests([tmp_path])
    except RegistryError as exc:
        message = str(exc)
    else:
        raise AssertionError("discover_tests should fail for missing data source")

    assert "Invalid data source for test_missing_data" in message
    assert "Data source not found" in message


def test_history_store_can_read_latest_and_run_by_id(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    run = AutoplatTestRunner(settings).run(suites)

    store = HistoryStore(tmp_path / "output" / "history.db")
    try:
        by_id = store.get_run(run.id)
        latest = store.get_latest_run()
    finally:
        store.close()

    assert by_id is not None
    assert by_id["run_id"] == run.id
    assert len(by_id["results"]) == 2
    assert latest is not None
    assert latest["run_id"] == run.id


def test_api_latest_run_falls_back_to_persisted_history(tmp_path: Path, monkeypatch) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    run = AutoplatTestRunner(settings).run(suites)

    (tmp_path / "autoplat.yaml").write_text(
        f"""
output:
  dir: {tmp_path / "output"}
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(endpoints, "_last_run", None)

    response = endpoints.get_run_results(run.id)
    latest = endpoints.get_latest_run()

    assert response["run_id"] == run.id
    assert response["total"] == 2
    assert response["results"][0]["name"] == "test_regression"
    assert latest["run_id"] == run.id


def test_in_process_failure_attaches_screenshot_artifact(tmp_path: Path, monkeypatch) -> None:
    task_file = tmp_path / "failing_task.py"
    task_file.write_text(
        """
from robocorp.tasks import task


@task
def test_fails():
    raise AssertionError("boom")
""",
        encoding="utf-8",
    )
    suites = discover_tests([tmp_path])
    settings = Settings.model_validate(
        {
            "execution": {"mode": "in-process"},
            "browser": {"screenshot": "only-on-failure"},
            "output": {"dir": tmp_path / "output", "report_format": "json"},
        }
    )

    def fake_capture_on_failure(test_name, error=None, output_dir=None):
        screenshot = output_dir / f"{test_name}.png"
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        screenshot.write_bytes(b"fake png")
        return screenshot

    monkeypatch.setattr("ui_autoplat.browser.screenshots.capture_on_failure", fake_capture_on_failure)

    run = AutoplatTestRunner(settings).run(suites)
    result = run.results[0]

    assert result.status == "failed"
    assert len(result.screenshots) == 1
    assert result.screenshots[0].exists()
    assert result.artifacts == result.screenshots

    report_path = JSONReportGenerator(settings.output).generate(run)
    report = report_path.read_text(encoding="utf-8")
    assert "artifacts" in report
    assert "test_fails.png" in report


def test_subprocess_artifact_collection_extracts_robolog_screenshot(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    test_case = suites[0].tests[0]
    settings = Settings.model_validate(
        {
            "execution": {"mode": "subprocess"},
            "output": {"dir": tmp_path / "platform-output"},
        }
    )
    runner = AutoplatTestRunner(settings)

    source_output = tmp_path / "output"
    source_output.mkdir()
    (source_output / "output.robolog").write_text(
        f'<img src="{MINIMAL_PNG_DATA_URI}"/>',
        encoding="utf-8",
    )
    now = datetime.now()
    result = AutoplatTestResult(
        test_case=test_case,
        status="failed",
        start_time=now,
        end_time=now,
        duration=0.1,
        error=AssertionError("boom"),
    )

    runner._attach_subprocess_artifacts(result)

    assert len(result.screenshots) == 1
    assert result.screenshots[0].exists()
    assert result.screenshots[0].suffix == ".png"
    assert result.screenshots[0] in result.artifacts


def test_subprocess_failure_prefers_real_error_over_stderr_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    task_file = tmp_path / "failure_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    test_case = suites[0].tests[0]
    settings = Settings.model_validate(
        {
            "execution": {"mode": "subprocess"},
            "output": {"dir": tmp_path / "output"},
        }
    )
    runner = AutoplatTestRunner(settings)

    stdout = """
Collecting task test_smoke from: failure_task.py
======================== Running: test_smoke ========================
test_smoke status: FAIL

Locator.wait_for: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("h1").filter(has_text="missing") to be visible

================ Full Traceback (running test_smoke) =================
Traceback (most recent call last):
  File "failure_task.py", line 10, in test_smoke
    locator.wait_for()
playwright._impl._errors.TimeoutError: Locator.wait_for: Timeout 3000ms exceeded.
Call log:
  - waiting for locator("h1").filter(has_text="missing") to be visible

Log (html): output/log.html
"""
    stderr = """
D:\\Python\\Lib\\site-packages\\robocorp\\tasks\\cli.py:65: Warning: Usage of the native system certificate stores can't be enabled
  _inject_truststore()
"""

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner._execute_subprocess_once(test_case)

    assert result.status == "failed"
    assert str(result.error) == (
        "playwright._impl._errors.TimeoutError: "
        "Locator.wait_for: Timeout 3000ms exceeded."
    )
    assert "Usage of the native system certificate stores" in (result.error_traceback or "")

    artifact_names = {artifact.name for artifact in result.artifacts}
    assert {"stdout.log", "stderr.log"} <= artifact_names
    artifact_dir = tmp_path / "output" / "artifacts" / test_case.suite_name / test_case.name
    assert (artifact_dir / "stdout.log").exists()
    assert (artifact_dir / "stderr.log").exists()


def test_console_reporter_prints_failure_summary_before_traceback(capsys) -> None:
    task_case = discover_tests([Path("tests/unit")])[0].tests[0]
    now = datetime.now()
    result = AutoplatTestResult(
        test_case=task_case,
        status="failed",
        start_time=now,
        end_time=now,
        duration=0.1,
        error=AssertionError("real failure"),
        error_traceback="warning only",
    )

    ConsoleReporter().test_finished(result)

    output = capsys.readouterr().out
    assert "real failure" in output
    assert "warning only" not in output


def test_history_api_preserves_artifact_paths(tmp_path: Path, monkeypatch) -> None:
    task_file = tmp_path / "failing_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    test_case = suites[0].tests[0]

    screenshot = tmp_path / "output" / "screenshots" / "failure.png"
    log_path = tmp_path / "output" / "artifacts" / "log.html"
    extra_artifact = tmp_path / "output" / "artifacts" / "output.robolog"
    for artifact in (screenshot, log_path, extra_artifact):
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("artifact", encoding="utf-8")

    now = datetime.now()
    result = AutoplatTestResult(
        test_case=test_case,
        status="failed",
        start_time=now,
        end_time=now,
        duration=0.1,
        error=AssertionError("boom"),
        screenshots=[screenshot],
        log_path=log_path,
        artifacts=[screenshot, log_path, extra_artifact],
    )
    run = AutoplatTestRun(
        environment=EnvironmentInfo.capture(),
        results=[result],
    )
    store = HistoryStore(tmp_path / "output" / "history.db")
    try:
        store.record_run(run)
    finally:
        store.close()

    (tmp_path / "autoplat.yaml").write_text(
        f"""
output:
  dir: {tmp_path / "output"}
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(endpoints, "_last_run", None)

    response = endpoints.get_run_results(run.id)
    api_result = response["results"][0]

    assert api_result["screenshots"] == [str(screenshot)]
    assert api_result["log"] == str(log_path)
    assert str(extra_artifact) in api_result["artifacts"]


def test_html_report_uses_relative_artifact_links(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    test_case = suites[0].tests[0]

    screenshot = tmp_path / "output" / "screenshots" / "failure.png"
    log_path = tmp_path / "output" / "artifacts" / "basic" / "test_smoke" / "log.html"
    extra_artifact = tmp_path / "output" / "artifacts" / "basic" / "test_smoke" / "output.robolog"
    stdout_log = tmp_path / "output" / "artifacts" / "basic" / "test_smoke" / "stdout.log"
    stderr_log = tmp_path / "output" / "artifacts" / "basic" / "test_smoke" / "stderr.log"
    for artifact in (screenshot, log_path, extra_artifact, stdout_log, stderr_log):
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("artifact", encoding="utf-8")

    now = datetime.now()
    result = AutoplatTestResult(
        test_case=test_case,
        status="failed",
        start_time=now,
        end_time=now,
        duration=0.1,
        error=AssertionError("boom"),
        error_traceback="full traceback",
        screenshots=[screenshot],
        log_path=log_path,
        artifacts=[screenshot, stdout_log, stderr_log, log_path, extra_artifact],
    )
    run = AutoplatTestRun(environment=EnvironmentInfo.capture(), results=[result])
    settings = Settings.model_validate({"output": {"dir": tmp_path / "output"}})

    report_path = HTMLReportGenerator(settings.output).generate(run)
    html = report_path.read_text(encoding="utf-8")

    assert 'href="../screenshots/failure.png"' in html
    assert '<img src="../screenshots/failure.png"' in html
    assert 'href="../artifacts/basic/test_smoke/log.html"' in html
    assert "Primary logs" in html
    assert "Raw process output" in html
    assert 'href="../artifacts/basic/test_smoke/stdout.log"' in html
    assert 'href="../artifacts/basic/test_smoke/stderr.log"' in html
    assert "Other artifacts" in html
    assert 'href="../artifacts/basic/test_smoke/output.robolog"' in html
    assert "Full traceback / raw output" in html
    assert 'data-status="failed"' in html
    assert "test_smoke" in html
    assert "sample_task.py" in html
    assert "smoke" in html
    assert "Slowest tests" in html
    assert f"{test_case.suite_name} / {test_case.name}" in html
    assert 'data-filter="failed">Failed (1)' in html
    assert 'id="test-search"' in html
    assert "No tests match the current filters." in html


def test_junit_report_includes_failures_and_artifacts(tmp_path: Path) -> None:
    task_file = tmp_path / "sample_task.py"
    _write_task_file(task_file)
    suites = discover_tests([tmp_path])
    test_case = suites[0].tests[0]

    screenshot = tmp_path / "output" / "screenshots" / "failure.png"
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    screenshot.write_text("artifact", encoding="utf-8")

    now = datetime.now()
    result = AutoplatTestResult(
        test_case=test_case,
        status="failed",
        start_time=now,
        end_time=now,
        duration=0.25,
        error=AssertionError("boom"),
        error_traceback="AssertionError: boom",
        screenshots=[screenshot],
        artifacts=[screenshot],
    )
    run = AutoplatTestRun(environment=EnvironmentInfo.capture(), results=[result])
    settings = Settings.model_validate({"output": {"dir": tmp_path / "output"}})

    report_path = JUnitReportGenerator(settings.output).generate(run)
    root = ET.parse(report_path).getroot()

    assert root.tag == "testsuite"
    assert root.attrib["tests"] == "1"
    assert root.attrib["failures"] == "1"
    testcase = root.find("testcase")
    assert testcase is not None
    assert testcase.attrib["name"] == test_case.name
    failure = testcase.find("failure")
    assert failure is not None
    assert failure.attrib["message"] == "boom"
    system_out = testcase.find("system-out")
    assert system_out is not None
    assert str(screenshot) in (system_out.text or "")
