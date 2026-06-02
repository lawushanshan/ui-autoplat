from __future__ import annotations

import importlib.util
import inspect
import re
import hashlib
from pathlib import Path
from typing import Any, Callable

from ui_autoplat.config.settings import DiscoveryConfig
from ui_autoplat.core.exceptions import DataDrivenError, RegistryError
from ui_autoplat.core.models import TestCase, TestSuite
from ui_autoplat.utils.data_driven import DataCase, expand_data_cases

_TASK_DECORATOR_ATTR = "_robocorp_task_metadata"


def _extract_docstring_tags(doc: str | None) -> list[str]:
    if not doc:
        return []
    tags = re.findall(r"Tags:\s*(.+)", doc)
    if not tags:
        return []
    return [t.strip() for t in tags[0].split(",")]


def _matches_tags(func_tags: list[str], tags: list[str], match_any: bool) -> bool:
    if not tags:
        return True
    if match_any:
        return any(t in func_tags for t in tags)
    return all(t in func_tags for t in tags)


def _expand_parameters(func: Callable[..., Any], base_dir: Path) -> list[DataCase | None]:
    source = getattr(func, "_data_source", None)
    if source is None:
        return [None]
    loader = getattr(func, "_data_loader", "auto")
    source = Path(source)
    if not source.is_absolute():
        source = base_dir / source
    try:
        data = expand_data_cases(source, loader=loader)
    except DataDrivenError as exc:
        raise RegistryError(f"Invalid data source for {func.__name__}: {exc}") from exc
    return data or [None]


def _extract_docstring_priority(doc: str | None) -> int:
    if not doc:
        return 3
    match = re.search(r"P(\d)", doc)
    if match:
        return int(match.group(1))
    return 3


def _is_task_function(func: Callable[..., Any]) -> bool:
    if not inspect.isfunction(func):
        return False
    if hasattr(func, _TASK_DECORATOR_ATTR):
        return True
    if func.__name__.startswith("test_"):
        return True
    return False


def _find_task_functions(module) -> list[Callable[..., Any]]:
    functions = []
    for _name, obj in inspect.getmembers(module, inspect.isfunction):
        if _is_task_function(obj):
            functions.append(obj)
    return functions


def _module_name_from_path(file_path: Path) -> str:
    resolved = str(file_path.resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:12]
    return f"_ui_autoplat_task_{file_path.stem}_{digest}"


def _import_module_from_file(file_path: Path):
    spec = importlib.util.spec_from_file_location(_module_name_from_path(file_path), file_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_tests(
    paths: list[Path],
    file_pattern: str = "*task*.py",
    tags: list[str] | None = None,
    priority_filter: list[int] | None = None,
    match_any_tag: bool = False,
) -> list[TestSuite]:
    suites: list[TestSuite] = []
    seen: set[tuple[Path, str]] = set()
    tags = tags or []
    priority_filter = priority_filter or []

    for base_path in paths:
        if not base_path.exists():
            continue

        if base_path.is_file():
            files = [base_path]
        else:
            files = sorted(base_path.rglob(file_pattern))

        for file_path in files:
            try:
                module = _import_module_from_file(file_path)
            except Exception as e:
                raise RegistryError(f"Failed to import {file_path}: {e}") from e

            if module is None:
                continue

            task_functions = _find_task_functions(module)
            if not task_functions:
                continue

            suite_name = file_path.stem.replace("_task", "").replace("_tasks", "")
            suite = TestSuite(name=suite_name, file_path=file_path)

            for func in task_functions:
                doc = func.__doc__ or ""
                func_tags = _extract_docstring_tags(doc)
                priority = _extract_docstring_priority(doc)

                if hasattr(func, "tags"):
                    func_tags.extend(func.tags)
                if hasattr(func, "priority"):
                    priority = func.priority

                if not _matches_tags(func_tags, tags, match_any_tag):
                    continue

                if priority_filter and priority not in priority_filter:
                    continue

                for data_case in _expand_parameters(func, file_path.parent):
                    name = func.__name__
                    parameters = None
                    case_id = None
                    case_name = None
                    skip_reason = None
                    if data_case is not None:
                        name = f"{func.__name__}[{data_case.display_name}]"
                        parameters = [data_case.row]
                        case_id = data_case.case_id
                        case_name = data_case.case_name
                        skip_reason = data_case.skip_reason

                    key = (file_path, name)
                    if key in seen:
                        continue
                    seen.add(key)

                    test_case = TestCase(
                        name=name,
                        function=func,
                        file_path=file_path,
                        suite_name=suite_name,
                        tags=func_tags,
                        priority=priority,
                        description=doc.strip().split("\n")[0] if doc else "",
                        parameters=parameters,
                        case_id=case_id,
                        case_name=case_name,
                        skip_reason=skip_reason,
                    )
                    suite.tests.append(test_case)

            if suite.tests:
                suites.append(suite)

    return suites


def discover_from_config(config: DiscoveryConfig) -> list[TestSuite]:
    return discover_tests(
        paths=config.paths,
        file_pattern=config.file_pattern,
        tags=config.tags or None,
        priority_filter=config.priority_filter or None,
    )
