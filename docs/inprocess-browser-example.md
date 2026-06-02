# In-Process Browser Example

This example verifies platform-managed browser lifecycle in `in-process` mode.

## Goal

The test file does not define a browser setup fixture. `ui-autoplat` configures browser context from `autoplat.yaml` before running the suite.

## Example

```text
examples/inprocess_browser/
  autoplat.yaml
  basic_task.py
```

## Commands

```bash
cd examples/inprocess_browser
autoplat discover . --format json
autoplat run . --config autoplat.yaml
```

Expected behavior:

- `test_example_title` is discovered.
- The browser is configured by `TestRunner` through `BrowserManager`.
- The test passes in headless Chromium.
- JSON report is written to `output/reports/results.json`.

## Notes

This example is intentionally in-process only. Subprocess mode remains closer to native Robocorp Tasks execution and can still use task-level setup functions.
