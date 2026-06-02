from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Generator


def load_csv(file_path: Path | str) -> list[dict[str, str]]:
    file_path = Path(file_path)
    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_json(file_path: Path | str) -> list[dict[str, Any]]:
    file_path = Path(file_path)
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return [data]


def data_driven(source: str | Path, loader: str = "auto"):
    """Decorator for data-driven tests.

    Usage:
        @data_driven("test_data/users.csv")
        @task
        def test_login(row):
            ...
    """
    source = Path(source)

    def decorator(func):
        func._data_source = source
        func._data_loader = loader
        return func

    return decorator


def get_test_data(source: Path | str, loader: str = "auto") -> list[dict[str, Any]]:
    source = Path(source)
    if loader == "auto":
        if source.suffix == ".csv":
            return load_csv(source)
        if source.suffix == ".json":
            return load_json(source)
        raise ValueError(f"Cannot auto-detect format for: {source}")
    if loader == "csv":
        return load_csv(source)
    if loader == "json":
        return load_json(source)
    raise ValueError(f"Unknown loader: {loader}")
