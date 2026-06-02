from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DataCase:
    index: int
    row: dict[str, Any]
    case_id: str | None = None
    case_name: str | None = None
    skip_reason: str | None = None

    @property
    def skipped(self) -> bool:
        return self.skip_reason is not None

    @property
    def display_name(self) -> str:
        label = self.case_id or self.case_name
        if label:
            return _safe_case_label(label)
        return str(self.index)


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


def expand_data_cases(source: Path | str, loader: str = "auto") -> list[DataCase]:
    rows = get_test_data(source, loader=loader)
    return [build_data_case(row, index) for index, row in enumerate(rows, start=1)]


def build_data_case(row: dict[str, Any], index: int) -> DataCase:
    if not isinstance(row, dict):
        row = {"value": row}
    skip_reason = _skip_reason(row)
    return DataCase(
        index=index,
        row=row,
        case_id=_optional_str(row.get("case_id")),
        case_name=_optional_str(row.get("case_name")),
        skip_reason=skip_reason,
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _skip_reason(row: dict[str, Any]) -> str | None:
    if not _is_truthy(row.get("skip")):
        return None
    reason = _optional_str(row.get("skip_reason"))
    return reason or "Skipped by data row"


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_case_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return label.strip("_") or "case"
