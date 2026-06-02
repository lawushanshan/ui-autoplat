"""Demo login test suite - demonstrates autoplat platform usage."""
from robocorp import browser
from robocorp.tasks import task, setup, teardown


@setup
def suite_setup(task):
    browser.configure(
        browser_engine="chromium",
        headless=True,
        screenshot="only-on-failure",
    )


@teardown
def suite_teardown(task):
    browser.close()


@task
def test_homepage_loads():
    """Verify the example.com homepage loads. Tags: smoke, P0"""
    browser.goto("https://example.com")
    page = browser.page()
    title = page.title()
    assert title, "Page should have a title"
    print(f"Page loaded: {title}")


@task
def test_domain_heading():
    """Verify the h1 heading contains domain text. Tags: smoke, P1"""
    browser.goto("https://example.com")
    page = browser.page()
    heading = page.locator("h1")
    assert heading.count() > 0, "Expected an h1 heading"
    text = heading.first.text_content()
    assert text, "Heading should have text content"
    print(f"Heading: {text}")
