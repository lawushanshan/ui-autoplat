from __future__ import annotations


class SoftAssertions:
    def __init__(self) -> None:
        self._failures: list[str] = []

    def assert_true(self, condition: bool, message: str = "") -> None:
        if not condition:
            self._failures.append(f"Expected True, got False. {message}")

    def assert_equals(self, actual, expected, message: str = "") -> None:
        if actual != expected:
            self._failures.append(f"Expected {expected!r}, got {actual!r}. {message}")

    def assert_contains(self, text: str, substring: str, message: str = "") -> None:
        if substring not in text:
            self._failures.append(f"Expected '{text}' to contain '{substring}'. {message}")

    def assert_visible(self, selector: str, timeout: float = 5.0, page=None) -> None:
        try:
            from ui_autoplat.assertions.web_assertions import assert_visible

            assert_visible(selector, timeout=timeout, page=page)
        except AssertionError as e:
            self._failures.append(f"Element {selector} should be visible: {e}")
        except Exception as e:
            self._failures.append(f"Error checking visibility of {selector}: {e}")

    def assert_not_visible(self, selector: str, timeout: float = 5.0, page=None) -> None:
        try:
            from ui_autoplat.assertions.web_assertions import assert_not_visible

            assert_not_visible(selector, timeout=timeout, page=page)
        except AssertionError as e:
            self._failures.append(f"Element {selector} should not be visible: {e}")
        except Exception as e:
            self._failures.append(f"Error checking visibility of {selector}: {e}")

    def assert_text_equals(self, selector: str, expected: str, timeout: float = 5.0, page=None) -> None:
        try:
            from ui_autoplat.assertions.web_assertions import assert_text_equals

            assert_text_equals(selector, expected, timeout=timeout, page=page)
        except AssertionError as e:
            self._failures.append(str(e))
        except Exception as e:
            self._failures.append(f"Error checking text for {selector}: {e}")

    @property
    def failures(self) -> list[str]:
        return list(self._failures)

    def assert_all(self) -> None:
        if self._failures:
            details = "\n  - ".join(self._failures)
            raise AssertionError(f"Soft assertion failures ({len(self._failures)}):\n  - {details}")
