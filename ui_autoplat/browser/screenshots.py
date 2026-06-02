from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


def _safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("_") or "screenshot"


def capture_screenshot(
    test_name: str = "",
    output_dir: Path = Path("output/screenshots"),
    page=None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if test_name:
        filename = f"{_safe_filename(test_name)}_{timestamp}.png"
    else:
        filename = f"screenshot_{timestamp}.png"

    filepath = output_dir / filename

    if page is not None:
        page.screenshot(path=str(filepath))
    else:
        try:
            from robocorp import browser

            browser.page().screenshot(path=str(filepath))
        except Exception:
            pass

    return filepath


def capture_on_failure(
    test_name: str,
    error: Exception | None = None,
    output_dir: Path = Path("output/screenshots"),
) -> Path | None:
    try:
        from robocorp import browser

        page = browser.page()
        return capture_screenshot(test_name=test_name, output_dir=output_dir, page=page)
    except Exception:
        return None
