from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from ui_autoplat.cli import cli


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


def test_discover_supports_run_filter_arguments(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    _write_task_file(tests_dir / "sample_task.py")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "discover",
            str(tests_dir),
            "--tags-any",
            "smoke,regression",
            "--priority",
            "P0",
            "--task",
            "test_smoke",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"name": "test_smoke"' in result.output
    assert '"name": "test_regression"' not in result.output


def test_report_command_supports_junit_format(tmp_path: Path) -> None:
    reports_dir = tmp_path / "output" / "reports"
    reports_dir.mkdir(parents=True)
    report_file = reports_dir / "junit.xml"
    report_file.write_text("<testsuite />", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "report",
            "--format",
            "junit",
            "--output-dir",
            str(tmp_path / "output"),
        ],
    )

    assert result.exit_code == 0
    assert str(report_file.resolve()) in result.output


def test_config_validate_accepts_valid_config_with_profile(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    config_file = tmp_path / "autoplat.yaml"
    config_file.write_text(
        f"""
browser:
  browser_type: chromium
execution:
  mode: subprocess
output:
  dir: {tmp_path / "output"}
discovery:
  paths:
    - {tests_dir}
profiles:
  headed:
    browser:
      headless: false
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "config",
            "validate",
            "--config",
            str(config_file),
            "--profile",
            "headed",
        ],
    )

    assert result.exit_code == 0
    assert "Configuration is valid." in result.output
    assert "Profile: headed" in result.output


def test_config_validate_rejects_invalid_setting_value(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    config_file = tmp_path / "autoplat.yaml"
    config_file.write_text(
        f"""
browser:
  browser_type: invalid
output:
  dir: {tmp_path / "output"}
discovery:
  paths:
    - {tests_dir}
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "config",
            "validate",
            "--config",
            str(config_file),
        ],
    )

    assert result.exit_code == 1
    assert "Invalid configuration:" in result.output
    assert "browser.browser_type" in result.output


def test_config_validate_rejects_missing_profile(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    config_file = tmp_path / "autoplat.yaml"
    config_file.write_text(
        f"""
output:
  dir: {tmp_path / "output"}
discovery:
  paths:
    - {tests_dir}
profiles:
  smoke:
    browser:
      headless: true
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "config",
            "validate",
            "--config",
            str(config_file),
            "--profile",
            "missing",
        ],
    )

    assert result.exit_code == 1
    assert "Profile not found: missing" in result.output


def test_config_validate_rejects_missing_discovery_path(tmp_path: Path) -> None:
    config_file = tmp_path / "autoplat.yaml"
    missing_dir = tmp_path / "missing-tests"
    config_file.write_text(
        f"""
output:
  dir: {tmp_path / "output"}
discovery:
  paths:
    - {missing_dir}
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "config",
            "validate",
            "--config",
            str(config_file),
        ],
    )

    assert result.exit_code == 1
    assert f"Discovery path not found: {missing_dir}" in result.output


def test_doctor_accepts_ready_environment_with_browser_check_skipped(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    config_file = tmp_path / "autoplat.yaml"
    config_file.write_text(
        f"""
output:
  dir: {tmp_path / "output"}
discovery:
  paths:
    - {tests_dir}
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "doctor",
            "--config",
            str(config_file),
            "--skip-browser",
        ],
    )

    assert result.exit_code == 0
    assert "Doctor checks:" in result.output
    assert "Environment looks ready." in result.output
    assert "Browser Binary" in result.output
    assert "Skipped by --skip-browser" in result.output


def test_doctor_rejects_missing_discovery_path(tmp_path: Path) -> None:
    config_file = tmp_path / "autoplat.yaml"
    missing_dir = tmp_path / "missing-tests"
    config_file.write_text(
        f"""
output:
  dir: {tmp_path / "output"}
discovery:
  paths:
    - {missing_dir}
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "doctor",
            "--config",
            str(config_file),
            "--skip-browser",
        ],
    )

    assert result.exit_code == 1
    assert "Environment is not ready." in result.output
    assert f"Discovery path not found: {missing_dir}" in result.output
