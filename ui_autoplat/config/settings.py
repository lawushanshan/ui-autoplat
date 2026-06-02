from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserConfig(BaseModel):
    browser_type: Literal["chromium", "firefox", "webkit"] = Field(
        default="chromium",
        validation_alias=AliasChoices("browser_type", "type"),
    )
    headless: bool = True
    screenshot: Literal["off", "on", "only-on-failure"] = "only-on-failure"
    slowmo: int = 0
    viewport: dict[str, int] = Field(default_factory=lambda: {"width": 1280, "height": 720})
    locale: str = "en-US"
    timezone: str = "America/New_York"
    record_video: bool = False


class ExecutionConfig(BaseModel):
    mode: Literal["subprocess", "in-process"] = "subprocess"
    max_parallel: int = 1
    retries: int = 0
    timeout_per_test: float = 300.0
    stop_on_first_failure: bool = False


class OutputConfig(BaseModel):
    dir: Path = Path("output")
    report_format: Literal["html", "json", "junit", "allure", "all"] = "html"
    keep_reports: int = 10


class DiscoveryConfig(BaseModel):
    paths: list[Path] = Field(default_factory=lambda: [Path("./tests")])
    file_pattern: str = "*task*.py"
    tags: list[str] = Field(default_factory=list)
    priority_filter: list[int] = Field(default_factory=list)


class ActionServerConfig(BaseModel):
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8080


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: Path = Path("output/autoplat.log")


class Settings(BaseSettings):
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    action_server: ActionServerConfig = Field(default_factory=ActionServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    model_config = SettingsConfigDict(env_prefix="AUTOPLAT_", env_nested_delimiter="_")
