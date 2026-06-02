from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    root_logger = logging.getLogger("ui_autoplat")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if root_logger.handlers:
        return

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"ui_autoplat.{name}")
