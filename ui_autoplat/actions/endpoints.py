from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ui_autoplat.config.loader import load_settings
from ui_autoplat.core.models import TestRun, TestSuite
from ui_autoplat.core.registry import discover_tests
from ui_autoplat.actions.server import APIError
from ui_autoplat.reporting.history import HistoryStore

_last_run: TestRun | None = None
_run_lock = threading.Lock()


@dataclass
class RunStatus:
    status: str = "idle"
    run_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    cancel_requested: bool = False


_run_status = RunStatus()
_status_lock = threading.Lock()


def get_health() -> dict[str, Any]:
    config = load_settings()
    return {
        "status": "ok",
        "output_dir": str(config.output.dir),
    }


def get_run_status() -> dict[str, Any]:
    with _status_lock:
        return _run_status_to_dict(_run_status)


def cancel_run() -> dict[str, Any]:
    with _status_lock:
        if _run_status.status != "running":
            raise APIError(409, "no_run_in_progress", "No test run is currently in progress")
        _run_status.cancel_requested = True
        return _run_status_to_dict(_run_status)


def trigger_test_run(
    suite_path: str,
    tags: str | None = None,
    task_name: str | None = None,
    async_run: bool | str = False,
) -> dict[str, Any]:
    """Trigger a test run and return results."""
    global _last_run

    config, suites = _prepare_run(suite_path=suite_path, tags=tags, task_name=task_name)

    if _parse_bool(async_run):
        with _status_lock:
            if _run_status.status == "running":
                raise APIError(409, "run_already_in_progress", "A test run is already in progress")
            _set_run_status_locked(status="running", run_id=None, error=None, cancel_requested=False)

        thread = threading.Thread(
            target=_run_suites_background,
            args=(config, suites),
            daemon=True,
        )
        thread.start()
        return {
            "accepted": True,
            "status": "running",
            "status_url": "/api/runs/status",
        }

    with _status_lock:
        if _run_status.status == "running":
            raise APIError(409, "run_already_in_progress", "A test run is already in progress")
        _set_run_status_locked(status="running", run_id=None, error=None, cancel_requested=False)

    try:
        run = _execute_suites(config, suites)
    except Exception as exc:
        with _status_lock:
            _set_run_status_locked(status="error", error=str(exc), finished_at=datetime.now())
        raise

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
    data = config.model_dump()
    if data.get("action_server", {}).get("auth_token"):
        data["action_server"]["auth_token"] = "***"
    return data


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


def _prepare_run(
    suite_path: str,
    tags: str | None = None,
    task_name: str | None = None,
) -> tuple[Any, list[TestSuite]]:
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

    return config, suites


def _execute_suites(config: Any, suites: list[TestSuite]) -> TestRun:
    global _last_run

    from ui_autoplat.core.runner import TestRunner

    with _run_lock:
        runner = TestRunner(config=config, should_cancel=_is_cancellation_requested)
        run = runner.run(suites)
        _last_run = run

    with _status_lock:
        final_status = "completed" if not run.has_failures else "failed"
        if _run_status.cancel_requested:
            final_status = "cancelled"
        _set_run_status_locked(
            status=final_status,
            run_id=run.id,
            finished_at=datetime.now(),
            error=None,
        )
    return run


def _run_suites_background(config: Any, suites: list[TestSuite]) -> None:
    try:
        _execute_suites(config, suites)
    except Exception as exc:
        with _status_lock:
            _set_run_status_locked(status="error", error=str(exc), finished_at=datetime.now())


def _is_cancellation_requested() -> bool:
    with _status_lock:
        return _run_status.cancel_requested


def _set_run_status_locked(
    status: str,
    run_id: str | None = None,
    error: str | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    cancel_requested: bool | None = None,
) -> None:
    _run_status.status = status
    if run_id is not None or status in {"idle", "running"}:
        _run_status.run_id = run_id
    if started_at is not None or status in {"idle", "running"}:
        _run_status.started_at = started_at or datetime.now()
    if status == "idle" and started_at is None:
        _run_status.started_at = None
    if finished_at is not None or status in {"idle", "running"}:
        _run_status.finished_at = finished_at
    _run_status.error = error
    if cancel_requested is not None:
        _run_status.cancel_requested = cancel_requested
    elif status == "idle":
        _run_status.cancel_requested = False


def _run_status_to_dict(status: RunStatus) -> dict[str, Any]:
    return {
        "status": status.status,
        "run_id": status.run_id,
        "started_at": status.started_at.isoformat() if status.started_at else None,
        "finished_at": status.finished_at.isoformat() if status.finished_at else None,
        "error": status.error,
        "cancel_requested": status.cancel_requested,
    }


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


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
