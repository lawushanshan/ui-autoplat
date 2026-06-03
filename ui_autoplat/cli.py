from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import click
from pydantic import ValidationError

from ui_autoplat import __version__

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _load_settings(
    config_path: Optional[str],
    profile: Optional[str],
    cli_overrides: dict[str, Any] | None,
) -> Any:
    from ui_autoplat.config.loader import load_settings

    return load_settings(
        config_path=Path(config_path) if config_path else None,
        profile_name=profile,
        cli_overrides=cli_overrides,
    )


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__, prog_name="autoplat")
def cli() -> None:
    """UI Automation Testing Platform built on robocorp-tasks and robocorp-browser."""


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.argument("path", default="./tests", required=False)
@click.option("-t", "--task", "task_name", help="Run only the named task")
@click.option("--tags", help="Filter by tags (comma-separated, AND logic)")
@click.option("--tags-any", "tags_any", help="Filter by tags (comma-separated, OR logic)")
@click.option("--priority", type=click.Choice(["P0", "P1", "P2", "P3"]), help="Filter by priority")
@click.option("--browser", type=click.Choice(["chromium", "firefox", "webkit"]), help="Browser engine")
@click.option("--headed", is_flag=True, help="Run with visible browser window")
@click.option("--slowmo", type=int, default=None, help="Slow actions by N milliseconds")
@click.option("--screenshot", type=click.Choice(["off", "on", "only-on-failure"]), help="Screenshot mode")
@click.option("--retries", type=int, default=None, help="Retry failed tests")
@click.option("--timeout", type=float, default=None, help="Per-test timeout in seconds")
@click.option("--stop-on-failure", is_flag=True, help="Abort run on first failure")
@click.option("--parallel", type=int, default=None, help="Max parallel test processes")
@click.option("--mode", type=click.Choice(["subprocess", "in-process"]), help="Execution mode")
@click.option("--report", "report_format", type=click.Choice(["html", "json", "junit", "allure", "all"]), help="Report format")
@click.option("--output-dir", type=click.Path(), help="Output directory")
@click.option("--profile", help="Use named config profile")
@click.option("--config", "config_path", type=click.Path(), help="Config file path")
@click.option("-v", "--verbose", is_flag=True, help="Verbose console output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress output except errors")
@click.option("--dry-run", is_flag=True, help="List tests without executing")
def run(
    path: str,
    task_name: Optional[str],
    tags: Optional[str],
    tags_any: Optional[str],
    priority: Optional[str],
    browser: Optional[str],
    headed: bool,
    slowmo: Optional[int],
    screenshot: Optional[str],
    retries: Optional[int],
    timeout: Optional[float],
    stop_on_failure: bool,
    parallel: Optional[int],
    mode: Optional[str],
    report_format: Optional[str],
    output_dir: Optional[str],
    profile: Optional[str],
    config_path: Optional[str],
    verbose: bool,
    quiet: bool,
    dry_run: bool,
) -> None:
    """Discover and execute test tasks."""
    from ui_autoplat.config.settings import Settings
    from ui_autoplat.core.registry import discover_tests
    from ui_autoplat.core.runner import TestRunner
    from ui_autoplat.reporting.html_report import HTMLReportGenerator
    from ui_autoplat.reporting.json_report import JSONReportGenerator
    from ui_autoplat.utils.logger import setup_logging

    overrides: dict[str, Any] = {}
    if browser:
        overrides.setdefault("browser", {})["browser_type"] = browser
    if headed:
        overrides.setdefault("browser", {})["headless"] = False
    if slowmo is not None:
        overrides.setdefault("browser", {})["slowmo"] = slowmo
    if screenshot:
        overrides.setdefault("browser", {})["screenshot"] = screenshot
    if retries is not None:
        overrides.setdefault("execution", {})["retries"] = retries
    if timeout is not None:
        overrides.setdefault("execution", {})["timeout_per_test"] = timeout
    if stop_on_failure:
        overrides.setdefault("execution", {})["stop_on_first_failure"] = True
    if parallel is not None:
        overrides.setdefault("execution", {})["max_parallel"] = parallel
    if mode:
        overrides.setdefault("execution", {})["mode"] = mode
    if report_format:
        overrides.setdefault("output", {})["report_format"] = report_format
    if output_dir:
        overrides.setdefault("output", {})["dir"] = Path(output_dir)

    settings = _load_settings(config_path, profile, overrides)

    setup_logging(settings.logging.level, settings.logging.file)

    target_path = Path(path)
    if not target_path.exists():
        click.echo(f"Error: Path not found: {target_path}", err=True)
        sys.exit(1)

    filter_tags: list[str] = []
    if tags:
        filter_tags = [t.strip() for t in tags.split(",")]

    if tags_any:
        tag_list = [t.strip() for t in tags_any.split(",")]
        filter_tags = tag_list

    priority_filter: list[int] = []
    if priority:
        priority_filter = [int(priority[1])]

    suites = discover_tests(
        paths=[target_path],
        file_pattern=settings.discovery.file_pattern,
        tags=filter_tags if (tags or tags_any) else None,
        priority_filter=priority_filter,
        match_any_tag=bool(tags_any),
    )

    all_tests = [tc for suite in suites for tc in suite.tests]

    if task_name:
        all_tests = [tc for tc in all_tests if tc.name == task_name or tc.name.startswith(f"{task_name}[")]
        suites = _filter_suites_to_tests(suites, all_tests)

    if not all_tests:
        click.echo(f"No tests found in {target_path}", err=True)
        sys.exit(1)

    if dry_run:
        _print_discovered(suites, all_tests, verbose)
        sys.exit(0)

    runner = TestRunner(config=settings)
    run_result = runner.run(suites)

    if settings.output.report_format in ("html", "all"):
        gen = HTMLReportGenerator(settings.output)
        report_path = gen.generate(run_result)
        if not quiet:
            click.echo(f"\nHTML report: {report_path}")

    if settings.output.report_format in ("json", "all"):
        gen = JSONReportGenerator(settings.output)
        report_path = gen.generate(run_result)
        if not quiet:
            click.echo(f"JSON report: {report_path}")

    if settings.output.report_format in ("junit", "all"):
        from ui_autoplat.reporting.junit_report import JUnitReportGenerator

        gen = JUnitReportGenerator(settings.output)
        report_path = gen.generate(run_result)
        if not quiet:
            click.echo(f"JUnit report: {report_path}")

    if settings.output.report_format in ("allure", "all"):
        try:
            from ui_autoplat.reporting.allure_adapter import AllureAdapter

            gen = AllureAdapter(settings.output)
            allure_dir = gen.generate(run_result)
            if not quiet:
                click.echo(f"Allure results: {allure_dir}")
                click.echo(f"  View with: allure serve {allure_dir}")
        except ImportError:
            if not quiet:
                click.echo("Allure adapter skipped (allure-pytest not installed)")

    if not quiet:
        click.echo(f"History: {settings.output.dir / 'history.db'}")

    sys.exit(1 if run_result.has_failures else 0)


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.argument("path", default="./tests", required=False)
@click.option("--tags", help="Filter by tags")
@click.option("--tags-any", "tags_any", help="Filter by tags (comma-separated, OR logic)")
@click.option("--priority", type=click.Choice(["P0", "P1", "P2", "P3"]), help="Filter by priority")
@click.option("-t", "--task", "task_name", help="Show only the named task")
@click.option("--format", "output_format", type=click.Choice(["table", "json", "tree"]), default="table")
@click.option("-v", "--verbose", is_flag=True, help="Show full details")
def discover(
    path: str,
    tags: Optional[str],
    tags_any: Optional[str],
    priority: Optional[str],
    task_name: Optional[str],
    output_format: str,
    verbose: bool,
) -> None:
    """List discovered tests without executing them."""
    from ui_autoplat.core.registry import discover_tests

    target_path = Path(path)
    filter_tags = [t.strip() for t in tags.split(",")] if tags else None
    match_any_tag = False
    if tags_any:
        filter_tags = [t.strip() for t in tags_any.split(",")]
        match_any_tag = True

    priority_filter: list[int] = []
    if priority:
        priority_filter = [int(priority[1])]

    suites = discover_tests(
        paths=[target_path],
        tags=filter_tags,
        priority_filter=priority_filter,
        match_any_tag=match_any_tag,
    )

    all_tests = [tc for suite in suites for tc in suite.tests]
    if task_name:
        all_tests = [tc for tc in all_tests if tc.name == task_name or tc.name.startswith(f"{task_name}[")]
        suites = _filter_suites_to_tests(suites, all_tests)

    if not all_tests:
        click.echo(f"No tests found in {target_path}")
        return

    _print_discovered(suites, all_tests, verbose, output_format)


def _filter_suites_to_tests(suites: list, tests: list) -> list:
    allowed = set(tests)
    filtered = []
    for suite in suites:
        suite_tests = [tc for tc in suite.tests if tc in allowed]
        if suite_tests:
            from ui_autoplat.core.models import TestSuite

            filtered.append(TestSuite(name=suite.name, file_path=suite.file_path, tests=suite_tests))
    return filtered


def _print_discovered(suites: list, all_tests: list, verbose: bool, fmt: str = "table") -> None:
    from ui_autoplat.core.models import TestSuite

    if fmt == "json":
        import json

        data = []
        for suite in suites:
            for tc in suite.tests:
                data.append({
                    "name": tc.name,
                    "suite": suite.name,
                    "file": str(tc.file_path),
                    "tags": tc.tags,
                    "priority": f"P{tc.priority}",
                    "description": tc.description,
                })
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return

    click.echo(f"\nDiscovered {len(all_tests)} test(s) in {len(suites)} suite(s):\n")

    for suite in suites:
        assert isinstance(suite, TestSuite)
        click.echo(f"  {suite.file_path.name} ({suite.name})")
        click.echo(f"  {'':>4}{'NAME':<40} {'PRI':<6} {'TAGS'}")
        click.echo(f"  {'':>4}{'-' * 40} {'-' * 6} {'-' * 20}")
        for tc in suite.tests:
            tag_str = ", ".join(tc.tags) if tc.tags else "-"
            click.echo(f"  {'':>4}{tc.name:<40} P{tc.priority:<5} {tag_str}")
            if verbose and tc.description:
                click.echo(f"  {'':>8}# {tc.description}")
        click.echo()


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.argument("project_name")
@click.option("--template", type=click.Choice(["basic", "ecommerce", "saas"]), default="basic")
@click.option("--output-dir", type=click.Path(), default=".")
def scaffold(project_name: str, template: str, output_dir: str) -> None:
    """Create a new test project from a template."""
    from ui_autoplat.scaffolding.generator import ScaffoldGenerator

    gen = ScaffoldGenerator()
    target = Path(output_dir) / project_name

    try:
        gen.generate(project_name=project_name, template=template, output_dir=Path(output_dir))
        click.echo(f"\nCreated test project: {target}")
        click.echo(f"\nNext steps:")
        click.echo(f"  cd {project_name}")
        click.echo(f"  pip install -e .")
        click.echo(f"  autoplat run --headed")
    except Exception as e:
        click.echo(f"Error creating project: {e}", err=True)
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.option("--template", type=click.Choice(["basic", "ecommerce", "saas"]), default="basic")
def init(template: str) -> None:
    """Initialize autoplat in the current directory."""
    from ui_autoplat.scaffolding.generator import ScaffoldGenerator

    gen = ScaffoldGenerator()

    try:
        gen.init_current_dir(template=template)
        click.echo("\nInitialized autoplat project in current directory.")
        click.echo("\nNext steps:")
        click.echo("  pip install -e .")
        click.echo("  autoplat run --headed")
    except Exception as e:
        click.echo(f"Error initializing: {e}", err=True)
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
def browser_install() -> None:
    """Install browser binaries via Playwright."""
    import subprocess

    click.echo("Installing browser binaries...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        click.echo("Chromium installed successfully.")
    except subprocess.CalledProcessError:
        click.echo("Error: Failed to install Chromium.", err=True)
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.option("--config", "config_path", type=click.Path(), help="Config file path")
@click.option("--profile", help="Validate with a named config profile")
@click.option("--skip-browser", is_flag=True, help="Skip Playwright browser binary checks")
@click.option("--strict", is_flag=True, help="Exit with failure when warnings are found")
def doctor(config_path: Optional[str], profile: Optional[str], skip_browser: bool, strict: bool) -> None:
    """Check whether the local environment is ready to run tests."""
    import importlib.util
    import platform

    checks: list[tuple[str, str, str]] = []

    def add(status: str, name: str, detail: str) -> None:
        checks.append((status, name, detail))

    python_version = sys.version_info
    python_label = platform.python_version()
    if python_version >= (3, 10):
        add("OK", "Python", f"{python_label} >= 3.10")
    else:
        add("FAIL", "Python", f"{python_label}; Python 3.10+ is required")

    required_modules = [
        ("robocorp.tasks", "Robocorp Tasks"),
        ("robocorp.browser", "Robocorp Browser"),
        ("playwright.sync_api", "Playwright"),
        ("pydantic", "Pydantic"),
        ("yaml", "PyYAML"),
    ]
    for module_name, label in required_modules:
        if importlib.util.find_spec(module_name) is None:
            add("FAIL", label, f"Python module not importable: {module_name}")
        else:
            add("OK", label, f"Python module available: {module_name}")

    settings = None
    try:
        settings = _load_settings(config_path, profile, None)
        add(
            "OK",
            "Configuration",
            (
                f"mode={settings.execution.mode}, browser={settings.browser.browser_type}, "
                f"output={settings.output.dir}"
            ),
        )
    except Exception as exc:
        add("FAIL", "Configuration", str(exc))

    if settings is not None:
        discovery_errors = _validate_discovery_paths(
            settings.discovery.paths,
            _resolve_config_path(config_path).parent,
            bool(config_path),
        )
        if discovery_errors:
            for error in discovery_errors:
                add("FAIL", "Discovery", error)
        else:
            add("OK", "Discovery", ", ".join(str(path) for path in settings.discovery.paths))

    if skip_browser:
        add("WARN", "Browser Binary", "Skipped by --skip-browser")
    elif settings is not None:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser_type = getattr(playwright, settings.browser.browser_type)
                executable_path = Path(browser_type.executable_path)
                if executable_path.exists():
                    add("OK", "Browser Binary", f"{settings.browser.browser_type}: {executable_path}")
                else:
                    add(
                        "WARN",
                        "Browser Binary",
                        f"{settings.browser.browser_type} not installed; run `autoplat browser-install`",
                    )
        except Exception as exc:
            add("WARN", "Browser Binary", f"Could not check browser binary: {exc}")

    click.echo("\nDoctor checks:\n")
    for status, name, detail in checks:
        click.echo(f"  [{status:<4}] {name:<18} {detail}")

    failures = [check for check in checks if check[0] == "FAIL"]
    warnings = [check for check in checks if check[0] == "WARN"]
    if failures or (strict and warnings):
        click.echo("\nEnvironment is not ready.")
        sys.exit(1)

    click.echo("\nEnvironment looks ready.")


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.option("--run-id", help="Specific run ID (default: latest)")
@click.option("--format", "report_format", type=click.Choice(["html", "json", "junit"]), default="html")
@click.option("--output-dir", type=click.Path(), help="Output directory")
@click.option("--open", "open_report", is_flag=True, help="Open report in browser")
def report(run_id: Optional[str], report_format: str, output_dir: Optional[str], open_report: bool) -> None:
    """Generate or view test reports."""
    click.echo("Report command - reads from latest output/reports/")
    if output_dir:
        reports_path = Path(output_dir) / "reports"
    else:
        reports_path = Path("output/reports")

    if report_format == "html":
        report_file = reports_path / "log.html"
    elif report_format == "json":
        report_file = reports_path / "results.json"
    else:
        report_file = reports_path / "junit.xml"

    if report_file.exists():
        click.echo(f"Report: {report_file.resolve()}")
        if open_report:
            import webbrowser

            webbrowser.open(f"file:///{report_file.resolve()}")
    else:
        click.echo(f"No report found at {report_file}", err=True)
        sys.exit(1)


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.option("--test", "test_name", help="Specific test name")
@click.option("--days", type=int, default=30, help="Time range in days")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table")
def history(test_name: Optional[str], days: int, output_format: str) -> None:
    """View test history and trends."""
    settings = _load_settings(None, None, None)
    from ui_autoplat.reporting.history import HistoryStore

    store = HistoryStore(db_path=settings.output.dir / "history.db")

    if output_format == "json":
        if test_name:
            data = store.get_pass_rate_trend(test_name=test_name, days=days)
            results = store.get_test_history(test_name=test_name, days=days)
        else:
            data = store.get_pass_rate_trend(days=days)
            results = store.get_test_history(days=days)
        flaky = store.get_flaky_tests(days=days)
        stats = store.get_stats(days=days)

        import json

        click.echo(json.dumps({"trend": data, "flaky": flaky, "recent": results, "stats": stats}, indent=2, ensure_ascii=False))
    else:
        stats = store.get_stats(days=min(days, 7))
        click.echo(f"\n  Statistics (last {stats['period_days']} days):")
        click.echo(f"    Total runs: {stats['total_runs']}")
        for s in stats["by_status"]:
            click.echo(f"    {s['status']}: {s['count']} (avg {s['avg_duration']}s)")

        trend = store.get_pass_rate_trend(test_name=test_name, days=days)
        if trend:
            label = test_name or "all tests"
            click.echo(f"\n  Pass rate trend ({label}, last {days} days):")
            for row in trend:
                bar_len = int(row["pass_rate"] / 5)
                bar = "#" * bar_len + "-" * (20 - bar_len)
                click.echo(f"    {row['date']}  [{bar}] {row['pass_rate']}% ({row['passed']}/{row['total']})")

        flaky = store.get_flaky_tests(days=days)
        if flaky:
            click.echo(f"\n  Flaky tests (last {days} days):")
            for f in flaky:
                click.echo(f"    {f['test_name']}: {f['pass_rate']}% ({f['passes']}/{f['total_runs']})")
        else:
            click.echo(f"\n  No flaky tests detected (last {days} days).")

    store.close()


@cli.group(context_settings=CONTEXT_SETTINGS)
def config_group() -> None:
    """Configuration management."""


@config_group.command("show")
def config_show() -> None:
    """Display current effective configuration."""
    settings = _load_settings(None, None, None)
    import json

    def _serialize(obj):
        if hasattr(obj, "__str__"):
            return str(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    click.echo(json.dumps(settings.model_dump(), indent=2, ensure_ascii=False, default=_serialize))


@config_group.command("validate", context_settings=CONTEXT_SETTINGS)
@click.option("--config", "config_path", type=click.Path(), help="Config file path")
@click.option("--profile", help="Validate with a named config profile")
@click.option(
    "--skip-paths",
    is_flag=True,
    help="Skip discovery path existence checks",
)
def config_validate(config_path: Optional[str], profile: Optional[str], skip_paths: bool) -> None:
    """Validate autoplat configuration before running tests."""
    from ui_autoplat.config.loader import load_config_file, load_settings

    errors: list[str] = []
    warnings: list[str] = []
    resolved_config_path = _resolve_config_path(config_path)

    try:
        raw_config = load_config_file(resolved_config_path)
    except Exception as exc:
        click.echo(f"Invalid configuration: failed to read config file: {exc}", err=True)
        sys.exit(1)

    if config_path and not resolved_config_path.exists():
        errors.append(f"Config file not found: {resolved_config_path}")

    if profile:
        profiles = raw_config.get("profiles", {})
        if profile not in profiles:
            available = ", ".join(profiles.keys()) or "none"
            errors.append(f"Profile not found: {profile} (available: {available})")

    settings = None
    try:
        settings = load_settings(
            config_path=resolved_config_path if config_path else None,
            profile_name=profile,
            cli_overrides=None,
        )
    except KeyError as exc:
        errors.append(str(exc).strip("'"))
    except ValidationError as exc:
        errors.extend(_format_validation_errors(exc))
    except Exception as exc:
        errors.append(f"Configuration could not be loaded: {exc}")

    if settings is not None and not skip_paths:
        errors.extend(_validate_discovery_paths(settings.discovery.paths, resolved_config_path.parent, bool(raw_config)))
        warnings.extend(_validate_output_paths([settings.output.dir, settings.logging.file]))

    if errors:
        click.echo("Invalid configuration:", err=True)
        for error in errors:
            click.echo(f"  - {error}", err=True)
        if warnings:
            click.echo("Warnings:", err=True)
            for warning in warnings:
                click.echo(f"  - {warning}", err=True)
        sys.exit(1)

    click.echo("Configuration is valid.")
    click.echo(f"Config file: {_describe_config_file(resolved_config_path, bool(raw_config))}")
    if profile:
        click.echo(f"Profile: {profile}")
    if settings is not None:
        click.echo(f"Discovery paths: {', '.join(str(p) for p in settings.discovery.paths)}")
        click.echo(f"Output directory: {settings.output.dir}")
    if warnings:
        click.echo("Warnings:")
        for warning in warnings:
            click.echo(f"  - {warning}")


def _resolve_config_path(config_path: Optional[str]) -> Path:
    if config_path:
        return Path(config_path)
    yaml_path = Path.cwd() / "autoplat.yaml"
    if yaml_path.exists():
        return yaml_path
    return Path.cwd() / "autoplat.yml"


def _describe_config_file(path: Path, found: bool) -> str:
    if found:
        return str(path)
    return f"{path} (not found, using defaults)"


def _format_validation_errors(exc: ValidationError) -> list[str]:
    messages = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        messages.append(f"{location}: {error['msg']}")
    return messages


def _validate_discovery_paths(paths: list[Path], config_dir: Path, has_config_file: bool) -> list[str]:
    errors = []
    for path in paths:
        candidates = [path]
        if not path.is_absolute() and has_config_file:
            candidates = [config_dir / path]
        if not any(candidate.exists() for candidate in candidates):
            errors.append(f"Discovery path not found: {path}")
    return errors


def _validate_output_paths(paths: list[Path]) -> list[str]:
    warnings = []
    for path in paths:
        parent = path.parent if path.suffix else path
        check_path = parent
        while not check_path.exists() and check_path != check_path.parent:
            check_path = check_path.parent
        if not check_path.exists():
            warnings.append(f"Output path parent does not exist: {path}")
        elif not check_path.is_dir():
            warnings.append(f"Output path parent is not a directory: {path}")
    return warnings


@config_group.command(context_settings=CONTEXT_SETTINGS)
@click.argument("key_value")
def config_set(key_value: str) -> None:
    """Set a configuration value (KEY=VALUE)."""
    if "=" not in key_value:
        click.echo("Error: Use KEY=VALUE format, e.g. browser.headless=false", err=True)
        sys.exit(1)

    key, value = key_value.split("=", 1)
    settings = _load_settings(None, None, None)

    keys = key.split(".")
    target = settings
    for k in keys[:-1]:
        if hasattr(target, k):
            target = getattr(target, k)
        else:
            click.echo(f"Error: Key path '{key}' not found", err=True)
            sys.exit(1)

    final_key = keys[-1]
    if not hasattr(target, final_key):
        click.echo(f"Error: Key '{final_key}' not found in {'.'.join(keys[:-1])}", err=True)
        sys.exit(1)

    old_value = getattr(target, final_key)
    field_type = type(old_value)

    try:
        if field_type == bool:
            new_value = value.lower() in ("true", "1", "yes")
        elif field_type == int:
            new_value = int(value)
        elif field_type == float:
            new_value = float(value)
        elif field_type == Path:
            new_value = Path(value)
        else:
            new_value = value
    except ValueError:
        click.echo(f"Error: Cannot convert '{value}' to {field_type.__name__}", err=True)
        sys.exit(1)

    click.echo(f"  {key}: {old_value} -> {new_value}")
    click.echo("Note: To persist, update your autoplat.yaml file.")


@config_group.group(context_settings=CONTEXT_SETTINGS)
def profile() -> None:
    """Named configuration profiles."""


@profile.command("list")
def profile_list() -> None:
    """List saved profiles."""
    from ui_autoplat.config.profiles import ProfileManager

    mgr = ProfileManager()
    available = mgr.available
    if not available:
        click.echo("No profiles defined in autoplat.yaml")
        return

    for name in available:
        p = mgr.get(name)
        desc = ""
        if p and "browser" in p:
            if p["browser"].get("headless") is False:
                desc = "headed browser"
            elif p["browser"].get("record_video"):
                desc = "with video recording"
        click.echo(f"  {name:<12} {desc}")


@cli.command(context_settings=CONTEXT_SETTINGS)
@click.option("--host", default="127.0.0.1", help="Bind host")
@click.option("--port", type=int, default=8080, help="Bind port")
@click.option("--open", "open_api", is_flag=True, help="Open API docs in browser")
def serve(host: str, port: int, open_api: bool) -> None:
    """Start the REST API server."""
    if open_api:
        import webbrowser
        import threading

        def _open():
            import time
            time.sleep(1)
            webbrowser.open(f"http://{host}:{port}/")

        threading.Thread(target=_open, daemon=True).start()

    from ui_autoplat.actions.server import start_server

    start_server(host=host, port=port)


if __name__ == "__main__":
    cli()
