# ui-autoplat

UI automation testing platform built on Robocorp Tasks and Robocorp Browser.

## Current Capabilities

- Test discovery for `@task` and `test_*` functions.
- Tag, priority, task-name, and data-driven discovery filters.
- Subprocess and in-process execution modes.
- Retry, timeout, stop-on-failure, and parallel subprocess execution.
- Headless browser execution through Robocorp Browser.
- HTML, JSON, JUnit, and Allure-compatible reports.
- Failure artifacts, screenshots, Robocorp logs, and SQLite history.
- PageObject helpers and web assertion DSL.
- Configuration validation through `autoplat config validate`.
- Basic API server for runs, history, stats, and config.

## Install

```bash
pip install -e .
autoplat browser-install
```

## Quick Start

Discover tests:

```bash
autoplat discover examples/page_object --format json
```

Validate config:

```bash
autoplat config validate --config examples/page_object/autoplat.yaml
```

Run an example:

```bash
cd examples/page_object
autoplat run . --config autoplat.yaml --report json
```

## Example PageObject

```python
from ui_autoplat.assertions import expect_text_contains
from ui_autoplat.browser.page_objects import BasePage


class LoginPage(BasePage):
    url = "https://example.test/login"
    username = "#username"
    password = "#password"
    submit = "button[type=submit]"

    def wait_for_ready(self) -> None:
        self.wait_visible(self.username)

    def login(self, username: str, password: str) -> "LoginPage":
        self.fill(self.username, username)
        self.fill(self.password, password)
        self.click(self.submit)
        return self


def test_login_success():
    LoginPage().goto().login("admin", "secret")
    expect_text_contains("h1", "Dashboard")
```

## Development

Run tests and compile checks:

```bash
python -m pytest -q --basetemp .pytest_tmp
python -m compileall ui_autoplat tests examples -q
```

## Roadmap

See [docs/iteration-roadmap.md](docs/iteration-roadmap.md).

## License

MIT License. See [LICENSE](LICENSE).
