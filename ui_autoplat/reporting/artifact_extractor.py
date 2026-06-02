from __future__ import annotations

import base64
import re
from pathlib import Path


_DATA_IMAGE_RE = re.compile(r'data:image/png;base64,([A-Za-z0-9+/=]+)')


def extract_png_screenshots_from_text(
    text: str,
    output_dir: Path,
    prefix: str,
    limit: int = 5,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshots: list[Path] = []

    for index, match in enumerate(_DATA_IMAGE_RE.finditer(text), start=1):
        if index > limit:
            break
        try:
            image_bytes = base64.b64decode(match.group(1), validate=True)
        except ValueError:
            continue
        if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            continue

        screenshot_path = output_dir / f"{prefix}_{index}.png"
        screenshot_path.write_bytes(image_bytes)
        screenshots.append(screenshot_path)

    return screenshots


def extract_png_screenshots_from_file(
    source: Path,
    output_dir: Path,
    prefix: str,
    limit: int = 5,
) -> list[Path]:
    if not source.exists():
        return []
    text = source.read_text(encoding="utf-8", errors="ignore")
    return extract_png_screenshots_from_text(text, output_dir=output_dir, prefix=prefix, limit=limit)
