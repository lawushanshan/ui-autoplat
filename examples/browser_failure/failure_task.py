"""Intentional browser failure example for artifact verification."""

from robocorp import browser
from robocorp.tasks import setup, task


@setup
def setup_browser(task):
    browser.configure(
        browser_engine="chromium",
        headless=True,
        screenshot="only-on-failure",
    )


@task
def test_missing_heading():
    """Intentional failure to verify screenshot and artifact capture. Tags: smoke, P1"""
    browser.goto("https://example.com")
    page = browser.page()

    missing_heading = page.locator("h1", has_text="This heading should not exist")
    missing_heading.wait_for(state="visible", timeout=3000)
