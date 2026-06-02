from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from ui_autoplat.config.settings import Settings


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config_file(path: Path | None = None) -> dict[str, Any]:
    if path is None:
        path = Path.cwd() / "autoplat.yaml"
    if not path.exists():
        path = Path.cwd() / "autoplat.yml"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(
    config_path: Path | None = None,
    profile_name: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> Settings:
    file_data = load_config_file(config_path)

    if profile_name and "profiles" in file_data:
        profile = file_data["profiles"].get(profile_name)
        if profile is None:
            available = ", ".join(file_data["profiles"].keys()) or "none"
            raise KeyError(f"Profile '{profile_name}' not found. Available: {available}")
        file_data = _deep_merge(file_data, profile)

    if cli_overrides:
        file_data = _deep_merge(file_data, cli_overrides)

    file_data.pop("profiles", None)

    return Settings.model_validate(file_data)
