from __future__ import annotations


class AutoPlatError(Exception):
    """Base exception for the platform."""


class TestExecutionError(AutoPlatError):
    """Raised during test execution."""


class BrowserNotAvailableError(TestExecutionError):
    """Browser failed to launch or crashed."""


class PageLoadTimeoutError(TestExecutionError):
    """Page did not load within the timeout."""


class ElementNotFoundError(TestExecutionError):
    """Selector matched no elements."""


class AssertionFailureError(TestExecutionError):
    """A platform assertion failed."""


class ConfigurationError(AutoPlatError):
    """Invalid configuration file or value."""


class RegistryError(AutoPlatError):
    """Test discovery failure."""


class ReportGenerationError(AutoPlatError):
    """Could not generate a report."""
