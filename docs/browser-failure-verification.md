# Browser Failure Verification

This guide verifies the failure-debugging workflow for a real browser test.

## Goal

Confirm that a browser failure produces useful diagnostic evidence:

- The test fails intentionally.
- Robocorp browser artifacts are generated.
- `ui-autoplat` collects artifacts into the configured output directory.
- HTML, JSON, JUnit, and Allure outputs expose the failure information.

## Example

The verification example lives at:

```text
examples/browser_failure/failure_task.py
```

It opens `https://example.com` and waits for a heading that does not exist.

## Commands

From the example directory:

```bash
cd examples/browser_failure
autoplat browser-install
autoplat discover . --format json
autoplat run . --config autoplat.yaml --report all
```

Expected behavior:

- The run exits with a non-zero exit code.
- `test_missing_heading` is reported as failed.
- Reports are generated under:

```text
examples/browser_failure/output/
  reports/
    log.html
    results.json
    junit.xml
  allure-results/
  artifacts/
  history.db
```

## Manual Checks

Open:

```text
examples/browser_failure/output/reports/log.html
```

Confirm:

- The failed test is visible.
- The error detail is visible.
- Artifact links are present.
- Links resolve relative to the report file.

Open:

```text
examples/browser_failure/output/reports/results.json
```

Confirm:

- `summary.failed` is at least `1`.
- The failed result contains `artifacts`.
- If Robocorp embedded a screenshot in `output.robolog`, the failed result contains `screenshots`.

Open:

```text
examples/browser_failure/output/reports/junit.xml
```

Confirm:

- `testsuite failures` is at least `1`.
- The testcase contains a `<failure>` node.
- Artifact paths appear in `<system-out>` if artifacts were collected.
- Screenshot paths appear in `<system-out>` when extracted.

## When User Involvement Is Needed

Manual involvement is needed if:

- Browser binaries are not installed and `autoplat browser-install` must be run.
- A visible browser run is required:

```bash
autoplat run . --config autoplat.yaml --headed --report all
```

- The generated HTML report needs visual inspection.

## Troubleshooting

If browser launch fails, install Chromium:

```bash
autoplat browser-install
```

The first browser install may download more than 100 MB. Complete this once before judging screenshot behavior.

If Robocorp embeds a screenshot in `output.robolog`, `ui-autoplat` extracts it to:

```text
output/screenshots/
```

If the test fails before opening a page, there may still be no screenshot. The error and Robocorp logs should still appear in reports and artifacts.
