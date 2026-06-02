"""In-process browser example configured by ui-autoplat."""

from robocorp import browser
from robocorp.tasks import task


@task
def test_example_title():
    """Verify example.com title without user browser setup. Tags: smoke, P1"""
    browser.goto("https://example.com")
    page = browser.page()

    assert page.title(), "Page should have a title"
