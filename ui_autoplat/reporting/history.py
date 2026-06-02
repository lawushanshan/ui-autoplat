from __future__ import annotations

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ui_autoplat.core.models import TestResult, TestRun, TestRunSummary


_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS test_runs (
    run_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    total INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    skipped INTEGER NOT NULL,
    error INTEGER NOT NULL,
    duration REAL NOT NULL,
    pass_rate REAL NOT NULL,
    environment TEXT
);

CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    test_name TEXT NOT NULL,
    suite_name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration REAL NOT NULL,
    error_message TEXT,
    retry_attempt INTEGER DEFAULT 0,
    case_id TEXT,
    case_name TEXT,
    parameters TEXT,
    skip_reason TEXT,
    screenshots TEXT,
    video_path TEXT,
    log_path TEXT,
    artifacts TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES test_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_results_run_id ON test_results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_test_name ON test_results(test_name);
CREATE INDEX IF NOT EXISTS idx_results_timestamp ON test_results(timestamp);
"""


class HistoryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path("output/history.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(_CREATE_TABLES)
            self._migrate_schema()
        return self._conn

    def _migrate_schema(self) -> None:
        assert self._conn is not None
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(test_results)").fetchall()
        }
        migrations = {
            "case_id": "ALTER TABLE test_results ADD COLUMN case_id TEXT",
            "case_name": "ALTER TABLE test_results ADD COLUMN case_name TEXT",
            "parameters": "ALTER TABLE test_results ADD COLUMN parameters TEXT",
            "skip_reason": "ALTER TABLE test_results ADD COLUMN skip_reason TEXT",
            "screenshots": "ALTER TABLE test_results ADD COLUMN screenshots TEXT",
            "video_path": "ALTER TABLE test_results ADD COLUMN video_path TEXT",
            "log_path": "ALTER TABLE test_results ADD COLUMN log_path TEXT",
            "artifacts": "ALTER TABLE test_results ADD COLUMN artifacts TEXT",
        }
        for column, statement in migrations.items():
            if column not in columns:
                self._conn.execute(statement)
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def record_run(self, run: TestRun) -> None:
        conn = self._get_conn()
        summary = run.summary
        env_info = ""
        if run.environment:
            env_info = f"os={run.environment.os};python={run.environment.python_version};browser={run.environment.browser_type}"

        conn.execute(
            """INSERT OR REPLACE INTO test_runs
               (run_id, timestamp, total, passed, failed, skipped, error, duration, pass_rate, environment)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run.id,
                run.timestamp.isoformat(),
                summary.total,
                summary.passed,
                summary.failed,
                summary.skipped,
                summary.error,
                summary.duration,
                summary.pass_rate,
                env_info,
            ),
        )

        for result in run.results:
            conn.execute(
                """INSERT INTO test_results
                   (run_id, test_name, suite_name, status, duration, error_message, retry_attempt,
                    case_id, case_name, parameters, skip_reason,
                    screenshots, video_path, log_path, artifacts, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run.id,
                    result.test_case.name,
                    result.test_case.suite_name,
                    result.status,
                    result.duration,
                    str(result.error) if result.error else None,
                    result.retry_attempt,
                    result.test_case.case_id,
                    result.test_case.case_name,
                    json.dumps(result.test_case.parameters[0], ensure_ascii=False)
                    if result.test_case.parameters
                    else None,
                    result.test_case.skip_reason,
                    json.dumps([str(p) for p in result.screenshots], ensure_ascii=False),
                    str(result.video_path) if result.video_path else None,
                    str(result.log_path) if result.log_path else None,
                    json.dumps([str(p) for p in result.artifacts], ensure_ascii=False),
                    run.timestamp.isoformat(),
                ),
            )

        conn.commit()

    def get_latest_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM test_runs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_run(self) -> dict[str, Any] | None:
        runs = self.get_latest_runs(limit=1)
        if not runs:
            return None
        return self.get_run(runs[0]["run_id"])

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        run_row = conn.execute(
            "SELECT * FROM test_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if run_row is None:
            return None

        result_rows = conn.execute(
            """SELECT test_name, suite_name, status, duration, error_message, retry_attempt,
                      case_id, case_name, parameters, skip_reason,
                      screenshots, video_path, log_path, artifacts, timestamp
               FROM test_results
               WHERE run_id = ?
               ORDER BY id""",
            (run_id,),
        ).fetchall()

        run = dict(run_row)
        run["results"] = [dict(r) for r in result_rows]
        return run

    def get_test_history(
        self,
        test_name: str | None = None,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        since = (datetime.now() - timedelta(days=days)).isoformat()

        if test_name:
            rows = conn.execute(
                """SELECT * FROM test_results
                   WHERE test_name = ? AND timestamp >= ?
                   ORDER BY timestamp DESC""",
                (test_name, since),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM test_results
                   WHERE timestamp >= ?
                   ORDER BY timestamp DESC""",
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_pass_rate_trend(self, test_name: str | None = None, days: int = 30) -> list[dict[str, Any]]:
        conn = self._get_conn()
        since = (datetime.now() - timedelta(days=days)).isoformat()

        if test_name:
            rows = conn.execute(
                """SELECT
                     date(timestamp) as date,
                     COUNT(*) as total,
                     SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
                     ROUND(SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pass_rate
                   FROM test_results
                   WHERE test_name = ? AND timestamp >= ?
                   GROUP BY date(timestamp)
                   ORDER BY date""",
                (test_name, since),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT
                     date(timestamp) as date,
                     COUNT(*) as total,
                     SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
                     ROUND(SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pass_rate
                   FROM test_results
                   WHERE timestamp >= ?
                   GROUP BY date(timestamp)
                   ORDER BY date""",
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_flaky_tests(self, days: int = 30, min_runs: int = 5) -> list[dict[str, Any]]:
        conn = self._get_conn()
        since = (datetime.now() - timedelta(days=days)).isoformat()

        rows = conn.execute(
            """SELECT
                 test_name,
                 COUNT(*) as total_runs,
                 SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passes,
                 SUM(CASE WHEN status IN ('failed', 'error') THEN 1 ELSE 0 END) as failures,
                 ROUND(SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as pass_rate
               FROM test_results
               WHERE timestamp >= ?
               GROUP BY test_name
               HAVING total_runs >= ? AND pass_rate > 30 AND pass_rate < 90
               ORDER BY pass_rate ASC""",
            (since, min_runs),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self, days: int = 7) -> dict[str, Any]:
        conn = self._get_conn()
        since = (datetime.now() - timedelta(days=days)).isoformat()

        run_row = conn.execute(
            "SELECT COUNT(*) as count FROM test_runs WHERE timestamp >= ?",
            (since,),
        ).fetchone()

        result_rows = conn.execute(
            """SELECT
                 status,
                 COUNT(*) as count,
                 ROUND(AVG(duration), 2) as avg_duration
               FROM test_results
               WHERE timestamp >= ?
               GROUP BY status""",
            (since,),
        ).fetchall()

        return {
            "period_days": days,
            "total_runs": dict(run_row)["count"],
            "by_status": [dict(r) for r in result_rows],
        }
