from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ui_autoplat.core.context import TestContext


class BasePage(ABC):
    url: str = ""
    context: "TestContext | None" = None
    default_timeout: float = 10.0

    def __init__(self, context: "TestContext | None" = None) -> None:
        self.context = context

    def load(self, url: str | None = None) -> BasePage:
        from robocorp import browser

        target_url = url or self.url
        if not target_url:
            raise ValueError("Page URL is not configured.")
        browser.goto(target_url)
        self.wait_for_ready()
        return self

    def goto(self, url: str | None = None) -> BasePage:
        return self.load(url)

    @abstractmethod
    def wait_for_ready(self) -> None:
        """Subclass defines readiness condition."""

    def is_loaded(self) -> bool:
        try:
            self.wait_for_ready()
            return True
        except Exception:
            return False

    @property
    def page(self):
        from robocorp import browser

        return browser.page()

    def locator(self, selector: str):
        return self.page.locator(selector)

    def wait_visible(self, selector: str, timeout: float | None = None) -> BasePage:
        self.locator(selector).wait_for(state="visible", timeout=self._timeout_ms(timeout))
        return self

    def wait_hidden(self, selector: str, timeout: float | None = None) -> BasePage:
        self.locator(selector).wait_for(state="hidden", timeout=self._timeout_ms(timeout))
        return self

    def click(self, selector: str, timeout: float | None = None, **kwargs: Any) -> BasePage:
        locator = self.locator(selector)
        locator.wait_for(state="visible", timeout=self._timeout_ms(timeout))
        locator.click(**kwargs)
        return self

    def fill(self, selector: str, value: str, timeout: float | None = None, **kwargs: Any) -> BasePage:
        locator = self.locator(selector)
        locator.wait_for(state="visible", timeout=self._timeout_ms(timeout))
        locator.fill(value, **kwargs)
        return self

    def select_option(
        self,
        selector: str,
        value: str | list[str],
        timeout: float | None = None,
        **kwargs: Any,
    ) -> BasePage:
        locator = self.locator(selector)
        locator.wait_for(state="visible", timeout=self._timeout_ms(timeout))
        locator.select_option(value, **kwargs)
        return self

    def text(self, selector: str, timeout: float | None = None) -> str:
        locator = self.locator(selector)
        locator.wait_for(state="visible", timeout=self._timeout_ms(timeout))
        return locator.text_content() or ""

    def screenshot(self, name: str = "", output_dir=None):
        from ui_autoplat.browser.screenshots import capture_screenshot

        if output_dir is None:
            return capture_screenshot(test_name=name, page=self.page)
        return capture_screenshot(test_name=name, output_dir=output_dir, page=self.page)

    def _timeout_ms(self, timeout: float | None) -> float:
        return (timeout if timeout is not None else self.default_timeout) * 1000


class PageFactory:
    @staticmethod
    def create(page_class: type[BasePage], context: "TestContext | None" = None) -> BasePage:
        return page_class(context=context)
