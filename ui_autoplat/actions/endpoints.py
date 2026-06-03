from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from ui_autoplat.config.loader import load_settings
from ui_autoplat.core.models import TestRun, TestSuite
from ui_autoplat.core.registry import discover_tests
from ui_autoplat.actions.server import APIError
from ui_autoplat.reporting.history import HistoryStore

_last_run: TestRun | None = None
_run_lock = threading.Lock()


def get_health() -> dict[str, Any]:
    config = load_settings()
    return {
        "status": "ok",
        "output_dir": str(config.output.dir),
    }


def trigger_test_run(
    suite_path: str,
    tags: str | None = None,
    task_name: str | None = None,
) -> dict[str, Any]:
    """Trigger a test run and return results."""
    global _last_run

    config = load_settings()
    if not suite_path:
        raise APIError(400, "missing_suite_path", "suite_path is required")
    target = Path(suite_path)
    if not target.exists():
        raise APIError(404, "suite_path_not_found", f"Suite path not found: {suite_path}")

    filter_tags = [t.strip() for t in tags.split(",")] if tags else None
    suites = discover_tests(paths=[target], tags=filter_tags)

    all_tests = [tc for suite in suites for tc in suite.tests]
    if task_name:
        all_tests = [tc for tc in all_tests if tc.name == task_name or tc.name.startswith(f"{task_name}[")]
        suites = _filter_suites_to_tests(suites, all_tests)
        if not all_tests:
            raise APIError(404, "test_not_found", f"Test not found: {task_name}")

    from ui_autoplat.core.runner import TestRunner

    with _run_lock:
        runner = TestRunner(config=config)
        run = runner.run(suites)
        _last_run = run

    return _run_to_dict(run)


def get_latest_run() -> dict[str, Any]:
    if _last_run is not None:
        return _run_to_dict(_last_run)

    persisted = _read_history_run()
    if persisted is None:
        raise APIError(404, "run_not_found", "No runs recorded yet")
    return _history_run_to_dict(persisted)


def get_run_results(run_id: str) -> dict[str, Any]:
    if _last_run is not None and _last_run.id == run_id:
        return _run_to_dict(_last_run)

    persisted = _read_history_run(run_id=run_id)
    if persisted is None:
        raise APIError(404, "run_not_found", f"Run {run_id} not found")
    return _history_run_to_dict(persisted)


def list_test_suites(suite_path: str = "./tests") -> dict[str, Any]:
    config = load_settings()
    target = Path(suite_path)
    if not target.exists():
        raise APIError(404, "suite_path_not_found", f"Suite path not found: {suite_path}")
    suites = discover_tests(paths=[target])

    result = []
    for suite in suites:
        all_tags = set()
        for tc in suite.tests:
            all_tags.update(tc.tags)
        result.append({
            "name": suite.name,
            "file_path": str(suite.file_path),
            "test_count": len(suite.tests),
            "tags": sorted(all_tags),
            "tests": [
                {
                    "name": tc.name,
                    "tags": tc.tags,
                    "priority": f"P{tc.priority}",
                    "description": tc.description,
                }
                for tc in suite.tests
            ],
        })
    return {"suites": result}


def get_history(test_name: str | None = None, days: int = 30) -> dict[str, Any]:
    config = load_settings()
    days = _parse_positive_int(days, "days")
    history = HistoryStore(db_path=config.output.dir / "history.db")

    if test_name:
        trend = history.get_pass_rate_trend(test_name=test_name, days=days)
        results = history.get_test_history(test_name=test_name, days=days)
    else:
        trend = history.get_pass_rate_trend(days=days)
        results = history.get_test_history(days=days)

    flaky = history.get_flaky_tests(days=days)

    history.close()
    return {"trend": trend, "flaky": flaky, "recent_results": results}


def get_stats(days: int = 7) -> dict[str, Any]:
    config = load_settings()
    days = _parse_positive_int(days, "days")
    history = HistoryStore(db_path=config.output.dir / "history.db")
    stats = history.get_stats(days=days)
    history.close()
    return stats


def get_config() -> dict[str, Any]:
    config = load_settings()
    return config.model_dump()


def _open_history() -> HistoryStore:
    config = load_settings()
    return HistoryStore(db_path=config.output.dir / "history.db")


def _read_history_run(run_id: str | None = None) -> dict[str, Any] | None:
    history = _open_history()
    try:
        if run_id is None:
            return history.get_latest_run()
        return history.get_run(run_id)
    finally:
        history.close()


def _filter_suites_to_tests(suites: list[TestSuite], tests: list) -> list[TestSuite]:
    allowed = set(tests)
    filtered: list[TestSuite] = []
    for suite in suites:
        suite_tests = [tc for tc in suite.tests if tc in allowed]
        if suite_tests:
            filtered.append(TestSuite(name=suite.name, file_path=suite.file_path, tests=suite_tests))
    return filtered


def _run_to_dict(run: TestRun) -> dict[str, Any]:
    summary = run.summary
    results_list = []
    for r in run.results:
        results_list.append({
            "name": r.test_case.name,
            "suite": r.test_case.suite_name,
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
        })

    return {
        "run_id": run.id,
        "timestamp": run.timestamp.isoformat(),
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "skipped": summary.skipped,
        "error": summary.error,
        "duration": round(summary.duration, 2),
        "pass_rate": summary.pass_rate,
        "results": results_list,
    }


def _history_run_to_dict(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "timestamp": run["timestamp"],
        "total": run["total"],
        "passed": run["passed"],
        "failed": run["failed"],
        "skipped": run["skipped"],
        "error": run["error"],
        "duration": round(run["duration"], 2),
        "pass_rate": run["pass_rate"],
        "environment": run.get("environment"),
        "results": [
            {
                "name": r["test_name"],
                "suite": r["suite_name"],
                "case_id": r.get("case_id"),
                "case_name": r.get("case_name"),
                "parameters": _loads_json_dict(r.get("parameters")),
                "skip_reason": r.get("skip_reason"),
                "status": r["status"],
                "duration": round(r["duration"], 2),
                "error": r["error_message"],
                "traceback": None,
                "screenshots": _loads_json_list(r.get("screenshots")),
                "video": r.get("video_path"),
                "log": r.get("log_path"),
                "artifacts": _loads_json_list(r.get("artifacts")),
                "retry_attempt": r["retry_attempt"],
            }
            for r in run["results"]
        ],
    }


def _loads_json_list(value: Any) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def _loads_json_dict(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _parse_positive_int(value: Any, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise APIError(400, "invalid_parameter", f"{name} must be an integer") from exc
    if parsed <= 0:
        raise APIError(400, "invalid_parameter", f"{name} must be greater than 0")
    return parsed
