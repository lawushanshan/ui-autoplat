# ui-autoplat Iteration Roadmap

## Current Position

The platform is currently a UI automation testing platform built around:

- Robocorp Tasks and Robocorp Browser as the execution foundation.
- `autoplat` CLI for discovery, execution, reports, history, config, scaffold, and API server.
- HTML, JSON, JUnit, and Allure-compatible report outputs.
- SQLite-backed history and persisted artifacts.
- In-process and subprocess execution modes.
- Data-driven test discovery and execution in in-process mode.
- Data-driven case metadata and row-level skip support.
- Basic API server for runs, suites, history, stats, and config.
- Configuration validation before execution through `autoplat config validate`.
- PageObject base helpers and web assertion DSL for test authoring.

## Completed

### Foundation

- Project architecture reviewed and documented.
- `docs/architecture.drawio` generated for diagrams.net / draw.io.
- Project-level `.gitignore` added.
- Mutable defaults in settings replaced with `Field(default_factory=...)`.

### Discovery

- Discovers `@task` and `test_*` functions.
- Supports tag filtering with AND logic via `--tags`.
- Supports tag filtering with OR logic via `--tags-any`.
- Supports priority filtering `P0` through `P3`.
- Supports task-name filtering.
- Supports data-driven expansion into `test_name[1]`, `test_name[2]`.
- Supports data-driven display names from `case_id` or `case_name`.
- Supports data-driven row skipping through `skip` and `skip_reason`.
- Resolves relative data files from the task file directory.
- Imports same-named task files from different directories as distinct modules.

### Execution

- Supports `subprocess` and `in-process` modes.
- Supports retry in both modes.
- Supports timeout in subprocess mode.
- Supports subprocess parallel execution through `max_parallel`.
- Keeps parallel subprocess results in discovery order.
- Resets runner state between repeated `run()` calls.
- Sets and clears `TestContext.current_test` and `TestContext.test_params` for in-process runs.

### Reporting And Artifacts

- HTML report.
- JSON report.
- JUnit XML report.
- Allure result adapter.
- Failure artifacts attached to `TestResult`.
- In-process failure screenshot capture hook.
- Subprocess Robocorp artifact collection.
- HTML report uses relative artifact links.
- JSON/API/JUnit reports expose artifact information.

### History And API

- SQLite history store.
- Run and test result persistence.
- Artifact paths persisted in history.
- Query latest run and run by ID from history.
- API falls back to persisted history when `_last_run` is empty.
- API dynamic route matching for `/api/runs/{run_id}`.

### CLI

- `run`, `discover`, `report`, `history`, `config`, `serve`, `scaffold`, `init`.
- `discover` filtering now aligns with `run`.
- `report --format html|json|junit`.
- JUnit report support for CI.
- `config validate` checks config loading, profile existence, schema values, discovery paths, and output path writability.
- `doctor` checks Python, key dependencies, configuration, discovery paths, and Playwright browser binaries.

### Test Authoring

- `BasePage` supports `goto`, `wait_visible`, `wait_hidden`, `click`, `fill`, `select_option`, `text`, and `screenshot`.
- Web assertions expose `assert_*` and `expect_*` helpers.
- Assertion failures include selector details and current page URL when available.
- PageObject example added under `examples/page_object`.

## Next Iterations

### 1. Real Browser Failure Verification

Goal: prove screenshot and artifact collection works in an actual browser session.

Tasks:

- Add a small intentional browser-failure example under `examples/`.
- Run it headed/headless.
- Confirm screenshot exists under `output/screenshots`.
- Confirm HTML/JSON/JUnit reports link or list the artifact.
- Confirm API returns artifact paths.

Status:

- Example added: `examples/browser_failure/failure_task.py`.
- Example config added: `examples/browser_failure/autoplat.yaml`.
- Verification guide added: `docs/browser-failure-verification.md`.
- Completed real browser headless verification.
- Verified HTML, JSON, JUnit, Robocorp log, artifact collection, and extracted PNG screenshot.
- Extracted screenshots from Robocorp `output.robolog` into `output/screenshots`.

Needs manual/user involvement:

- Yes, if we need to visually inspect the opened browser or generated report.

### 2. Browser Lifecycle Integration

Goal: make browser setup/cleanup more platform-controlled.

Tasks:

- Decide how much browser configuration should be handled by platform vs user task files.
- Add helper fixture APIs for browser setup.
- Ensure browser closes reliably after failures.
- Consider a platform-level `BrowserManager` integration path for in-process mode.

Status:

- Started.
- `BrowserManager` now uses capability-based close handling for current Robocorp Browser versions.
- `BrowserManager.configure()` now applies context settings: viewport, locale, timezone, and video directory.
- `TestRunner` now configures and closes `BrowserManager` around in-process suite execution.
- Added `examples/inprocess_browser` to demonstrate in-process browser tests without user-defined browser setup.

Needs manual/user involvement:

- Possibly, for real browser execution verification.

### 3. PageObject And Assertion DSL

Goal: make test authoring easier and more consistent.

Tasks:

- Expand `BasePage`.
- Add common action helpers.
- Improve web assertions with better error messages and screenshots.
- Add locator naming conventions.
- Add sample PageObject project template.

Status:

- Started.
- `BasePage` common action helpers added.
- Web assertion DSL improved with `expect_*` aliases and clearer failure context.
- Added `examples/page_object`.
- Verified `examples/page_object` with a real headless browser run.

Needs manual/user involvement:

- Optional, for reviewing whether the PageObject writing style feels natural.

### 4. Data-Driven Improvements

Goal: make data-driven tests production-ready.

Tasks:

- Add case ID/name support from data rows.
- Support skipping rows.
- Support CSV/JSON validation.
- Include data row metadata in reports.
- Consider subprocess-mode support strategy.

Status:

- Started.
- `case_id` and `case_name` are used in discovered test names.
- Data rows can set `skip: true` and `skip_reason`.
- CSV and JSON data files now fail fast with clear validation errors.
- JSON, JUnit, HTML, history, and API outputs include data case metadata.
- Added `examples/data_driven`.

Needs manual/user involvement:

- No.

### 5. API Server Hardening

Goal: make `autoplat serve` useful for dashboards and external systems.

Tasks:

- Add request/response schema validation.
- Add run status while a run is executing.
- Add run cancellation or queueing strategy.
- Add better error codes.
- Add optional auth/token support.
- Add API tests using a local HTTP server.

Status:

- Started.
- Added structured API errors with HTTP status codes.
- Added `/api/health`.
- Added parameter validation for `days` query values.
- Added path/run-not-found handling with 404 responses.
- Added local HTTP server tests for health, 400, and 404 responses.

Needs manual/user involvement:

- No initially.

### 6. CI/CD Integration

Goal: make the platform easy to use in real pipelines.

Tasks:

- Add example CI config.
- Document artifact paths.
- Document JUnit usage.
- Add exit code behavior docs.
- Add `autoplat doctor` for environment checks.

Status:

- Started.
- `autoplat doctor` added for local environment readiness checks.
- Manual acceptance checklist added at `docs/manual-acceptance-test.md`.
- Chinese CI/CD guide added at `docs/ci-cd.md`.
- GitHub Actions example workflow added at `.github/workflows/autoplat.yml`.
- Artifact paths, JUnit report usage, exit code behavior, and parallel execution notes documented.

Needs manual/user involvement:

- Possibly, if validating against a specific CI system.

### 7. Report UX Improvements

Goal: improve diagnosis speed.

Tasks:

- Add collapsible errors in HTML report.
- Add filter by status/tag/priority.
- Add artifact preview for screenshots.
- Add historical comparison summary.
- Add slow-test section.

Status:

- Started.
- HTML report now includes status filters, search, matched count, empty state, and a slowest-tests section.
- HTML report shows screenshot previews and groups diagnostic artifacts into primary logs, raw process output, and other artifacts.

Needs manual/user involvement:

- Useful for visual review.

### 8. Configuration And Profiles

Goal: make config safer and easier to understand.

Tasks:

- Add `autoplat config validate`.
- Add effective config source explanation.
- Persist `config set` optionally.
- Improve profile listing details.
- Document environment variable overrides.

Status:

- Started.
- `autoplat config validate` added.
- Config loading now removes `profiles` before validating effective settings.
- Missing profile names now fail explicitly instead of silently using base config.
- Existing example configs verified with `autoplat config validate`.

Needs manual/user involvement:

- No.

### 9. Optional AI-Assisted Analysis

Goal: add optional, non-core LLM analysis after deterministic execution is stable.

Tasks:

- Add `ai.enabled: false` config.
- Summarize failed runs from JSON/history/artifacts.
- Generate `ai_summary.md`.
- Add redaction before sending data externally.
- Keep pass/fail decisions deterministic and non-AI.

Needs manual/user involvement:

- Yes, for provider/model/API key choices and privacy policy.

## Recommended Next Step

Proceed with **manual acceptance testing** using `docs/manual-acceptance-test.md`.

The browser failure chain, browser lifecycle, PageObject example, and data-driven example are now ready for hands-on validation:

```text
write maintainable PageObjects -> use platform assertions -> run autoplat -> diagnose through reports/artifacts
```
