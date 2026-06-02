from __future__ import annotations

from typing import Any, Callable

from ui_autoplat.core.context import TestContext

SetupFunc = Callable[..., Any]
TeardownFunc = Callable[..., Any]


class FixtureManager:
    def __init__(self) -> None:
        self._suite_setups: list[SetupFunc] = []
        self._suite_teardowns: list[TeardownFunc] = []
        self._task_setups: list[SetupFunc] = []
        self._task_teardowns: list[TeardownFunc] = []

    def register_suite_setup(self, func: SetupFunc) -> None:
        self._suite_setups.append(func)

    def register_suite_teardown(self, func: TeardownFunc) -> None:
        self._suite_teardowns.append(func)

    def register_task_setup(self, func: SetupFunc) -> None:
        self._task_setups.append(func)

    def register_task_teardown(self, func: TeardownFunc) -> None:
        self._task_teardowns.append(func)

    def run_setup(self, scope: str, context: TestContext) -> None:
        funcs = self._suite_setups if scope == "suite" else self._task_setups
        for func in funcs:
            try:
                func()
            except Exception:
                pass

    def run_teardown(self, scope: str, context: TestContext) -> None:
        funcs = reversed(self._suite_teardowns if scope == "suite" else self._task_teardowns)
        for func in funcs:
            try:
                func()
            except Exception:
                pass
