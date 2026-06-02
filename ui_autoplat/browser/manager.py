from __future__ import annotations

from pathlib import Path
from typing import Any

from ui_autoplat.config.settings import BrowserConfig


class BrowserManager:
    def __init__(self, config: BrowserConfig, output_dir: Path = Path("output")) -> None:
        self._config = config
        self._output_dir = output_dir
        self._configured = False

    def configure(self, **overrides: Any) -> None:
        from robocorp import browser

        browser_kwargs = {
            "browser_engine": self._config.browser_type,
            "headless": self._config.headless,
            "screenshot": self._config.screenshot,
            "slowmo": self._config.slowmo,
        }

        if overrides:
            browser_kwargs.update(overrides)

        viewport = browser_kwargs.pop("viewport", None)
        if viewport is None:
            viewport = self._config.viewport

        browser.configure(**browser_kwargs)
        context_kwargs: dict[str, Any] = {
            "viewport": viewport,
            "locale": self._config.locale,
            "timezone_id": self._config.timezone,
        }
        if self._config.record_video:
            context_kwargs["record_video_dir"] = str(self._output_dir / "videos")

        browser.configure_context(**context_kwargs)
        self._configured = True

    def page(self):
        from robocorp import browser

        return browser.page()

    def new_context(self, **kwargs: Any):
        from robocorp import browser

        if not self._configured:
            self.configure()
        return browser.new_context(**kwargs)

    def goto(self, url: str) -> None:
        from robocorp import browser

        if not self._configured:
            self.configure()
        browser.goto(url)

    def screenshot(self, path: Path | None = None) -> Path:
        from robocorp import browser

        page = browser.page()
        if path is None:
            path = Path("output/screenshots") / f"screenshot_{id(page)}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(path))
        return path

    def close(self) -> None:
        try:
            from robocorp import browser

            close = getattr(browser, "close", None)
            if callable(close):
                close()
                return

            context = getattr(browser, "context", None)
            if callable(context):
                ctx = context()
                ctx_close = getattr(ctx, "close", None)
                if callable(ctx_close):
                    ctx_close()
        except Exception:
            pass
        finally:
            self._configured = False
