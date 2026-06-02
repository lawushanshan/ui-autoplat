from __future__ import annotations

def _get_page(page=None):
    if page is not None:
        return page
    from robocorp import browser

    return browser.page()


def _timeout_ms(timeout: float) -> float:
    return timeout * 1000


def _page_context(page) -> str:
    try:
        url = getattr(page, "url", "")
    except Exception:
        url = ""
    return f" Current URL: {url}" if url else ""


def _fail(message: str, page=None) -> None:
    raise AssertionError(f"{message}{_page_context(page)}")


def assert_visible(selector: str, timeout: float = 10.0, page=None) -> None:
    page = _get_page(page)
    locator = page.locator(selector)
    try:
        locator.wait_for(state="visible", timeout=_timeout_ms(timeout))
        if not locator.is_visible():
            _fail(f"Element should be visible: {selector}", page)
    except AssertionError:
        raise
    except Exception as exc:
        _fail(f"Element did not become visible: {selector}. Error: {exc}", page)


def assert_not_visible(selector: str, timeout: float = 10.0, page=None) -> None:
    page = _get_page(page)
    locator = page.locator(selector)
    try:
        locator.wait_for(state="hidden", timeout=_timeout_ms(timeout))
    except Exception:
        pass
    try:
        if locator.is_visible():
            _fail(f"Element should not be visible: {selector}", page)
    except AssertionError:
        raise
    except Exception as exc:
        _fail(f"Could not check element visibility: {selector}. Error: {exc}", page)


def assert_text_equals(selector: str, expected: str, timeout: float = 10.0, page=None) -> None:
    actual = _visible_text(selector, timeout=timeout, page=page)
    if actual != expected:
        page = _get_page(page)
        _fail(
            f"Text mismatch for {selector}: expected {expected!r}, got {actual!r}",
            page,
        )


def assert_text_contains(selector: str, substring: str, timeout: float = 10.0, page=None) -> None:
    actual = _visible_text(selector, timeout=timeout, page=page)
    if substring not in actual:
        page = _get_page(page)
        _fail(
            f"Text for {selector} should contain {substring!r}, got {actual!r}",
            page,
        )


def assert_element_count(selector: str, expected_count: int, timeout: float = 10.0, page=None) -> None:
    page = _get_page(page)
    locator = page.locator(selector)
    try:
        locator.first.wait_for(state="attached", timeout=_timeout_ms(timeout))
        actual_count = locator.count()
    except Exception as exc:
        _fail(f"Could not count elements for {selector}. Error: {exc}", page)
    if actual_count != expected_count:
        _fail(
            f"Element count mismatch for {selector}: expected {expected_count}, got {actual_count}",
            page,
        )


def assert_page_title(expected: str, timeout: float = 10.0, page=None) -> None:
    page = _get_page(page)
    page.wait_for_timeout(_timeout_ms(timeout))
    actual = page.title()
    if actual != expected:
        _fail(f"Page title mismatch: expected {expected!r}, got {actual!r}", page)


def assert_url_contains(substring: str, timeout: float = 10.0, page=None) -> None:
    page = _get_page(page)
    try:
        page.wait_for_url(f"**/{substring}**", timeout=_timeout_ms(timeout))
    except Exception:
        pass
    actual = page.url
    if substring not in actual:
        _fail(f"URL should contain {substring!r}, got {actual!r}", page)


def assert_url_equals(expected: str, timeout: float = 10.0, page=None) -> None:
    page = _get_page(page)
    try:
        page.wait_for_url(expected, timeout=_timeout_ms(timeout))
    except Exception:
        pass
    actual = page.url
    if actual != expected:
        _fail(f"URL mismatch: expected {expected!r}, got {actual!r}", page)


def assert_attribute_equals(
    selector: str,
    name: str,
    expected: str,
    timeout: float = 10.0,
    page=None,
) -> None:
    page = _get_page(page)
    locator = page.locator(selector)
    try:
        locator.wait_for(state="attached", timeout=_timeout_ms(timeout))
        actual = locator.get_attribute(name)
    except Exception as exc:
        _fail(f"Could not read attribute {name!r} from {selector}. Error: {exc}", page)
    if actual != expected:
        _fail(
            f"Attribute mismatch for {selector}[{name}]: expected {expected!r}, got {actual!r}",
            page,
        )


def assert_value_equals(selector: str, expected: str, timeout: float = 10.0, page=None) -> None:
    page = _get_page(page)
    locator = page.locator(selector)
    try:
        locator.wait_for(state="visible", timeout=_timeout_ms(timeout))
        actual = locator.input_value()
    except Exception as exc:
        _fail(f"Could not read input value for {selector}. Error: {exc}", page)
    if actual != expected:
        _fail(f"Value mismatch for {selector}: expected {expected!r}, got {actual!r}", page)


def _visible_text(selector: str, timeout: float, page=None) -> str:
    page = _get_page(page)
    locator = page.locator(selector)
    try:
        locator.wait_for(state="visible", timeout=_timeout_ms(timeout))
        return locator.text_content() or ""
    except Exception as exc:
        _fail(f"Could not read visible text for {selector}. Error: {exc}", page)
    raise AssertionError("unreachable")


def expect_visible(selector: str, timeout: float = 10.0, page=None) -> None:
    assert_visible(selector, timeout=timeout, page=page)


def expect_not_visible(selector: str, timeout: float = 10.0, page=None) -> None:
    assert_not_visible(selector, timeout=timeout, page=page)


def expect_text(selector: str, expected: str, timeout: float = 10.0, page=None) -> None:
    assert_text_equals(selector, expected, timeout=timeout, page=page)


def expect_text_contains(selector: str, substring: str, timeout: float = 10.0, page=None) -> None:
    assert_text_contains(selector, substring, timeout=timeout, page=page)


def expect_count(selector: str, expected_count: int, timeout: float = 10.0, page=None) -> None:
    assert_element_count(selector, expected_count, timeout=timeout, page=page)


def expect_title(expected: str, timeout: float = 10.0, page=None) -> None:
    assert_page_title(expected, timeout=timeout, page=page)


def expect_url_contains(substring: str, timeout: float = 10.0, page=None) -> None:
    assert_url_contains(substring, timeout=timeout, page=page)


def expect_url(expected: str, timeout: float = 10.0, page=None) -> None:
    assert_url_equals(expected, timeout=timeout, page=page)


def expect_attribute(
    selector: str,
    name: str,
    expected: str,
    timeout: float = 10.0,
    page=None,
) -> None:
    assert_attribute_equals(selector, name, expected, timeout=timeout, page=page)


def expect_value(selector: str, expected: str, timeout: float = 10.0, page=None) -> None:
    assert_value_equals(selector, expected, timeout=timeout, page=page)


__all__ = [
    "assert_attribute_equals",
    "assert_element_count",
    "assert_not_visible",
    "assert_page_title",
    "assert_text_contains",
    "assert_text_equals",
    "assert_url_contains",
    "assert_url_equals",
    "assert_value_equals",
    "assert_visible",
    "expect_attribute",
    "expect_count",
    "expect_not_visible",
    "expect_text",
    "expect_text_contains",
    "expect_title",
    "expect_url",
    "expect_url_contains",
    "expect_value",
    "expect_visible",
]
