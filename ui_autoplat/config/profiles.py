from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ui_autoplat.config.loader import _deep_merge


class ProfileManager:
    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is None:
            config_path = Path.cwd() / "autoplat.yaml"
        self._config_path = config_path
        self._profiles: dict[str, dict[str, Any]] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        if not self._config_path.exists():
            return
        with open(self._config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._profiles = data.get("profiles", {})

    @property
    def available(self) -> list[str]:
        return list(self._profiles.keys())

    def get(self, name: str) -> dict[str, Any] | None:
        return self._profiles.get(name)

    def apply(self, name: str, base: dict[str, Any]) -> dict[str, Any]:
        profile = self.get(name)
        if profile is None:
            raise KeyError(f"Profile '{name}' not found. Available: {self.available}")
        return _deep_merge(base, profile)
