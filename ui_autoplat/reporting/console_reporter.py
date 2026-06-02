from __future__ import annotations

from ui_autoplat.core.models import TestResult, TestRunSummary

_COLOR_GREEN = "\033[92m"
_COLOR_RED = "\033[91m"
_COLOR_YELLOW = "\033[93m"
_COLOR_CYAN = "\033[96m"
_COLOR_BOLD = "\033[1m"
_COLOR_RESET = "\033[0m"


class ConsoleReporter:
    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose
        self._test_count = 0
        self._passed = 0
        self._failed = 0

    def run_started(self, total: int) -> None:
        self._test_count = total
        self._passed = 0
        self._failed = 0
        print(f"\n{_COLOR_BOLD}Starting test run: {total} test(s){_COLOR_RESET}\n")

    def test_started(self, test) -> None:
        if self._verbose:
            from ui_autoplat.core.models import TestCase

            assert isinstance(test, TestCase)
            print(f"  Running: {test.name} ...", end="", flush=True)

    def test_finished(self, result: TestResult) -> None:
        name = result.test_case.name
        duration_str = f"{result.duration:.1f}s"

        if result.status == "passed":
            self._passed += 1
            print(f"  {_COLOR_GREEN}PASS{_COLOR_RESET} {name} ({duration_str})")
        elif result.status == "skipped":
            print(f"  {_COLOR_YELLOW}SKIP{_COLOR_RESET} {name}")
        else:
            self._failed += 1
            print(f"  {_COLOR_RED}FAIL{_COLOR_RESET} {name} ({duration_str})")
            if result.error_traceback:
                lines = result.error_traceback.strip().split("\n")
                for line in lines[-3:]:
                    print(f"       {line}")
            elif result.error:
                print(f"       {type(result.error).__name__}: {result.error}")

    def run_finished(self, results: list[TestResult]) -> None:
        summary = TestRunSummary.from_results(results)
        print()

        if summary.total == 0:
            print(f"  {_COLOR_YELLOW}No tests discovered.{_COLOR_RESET}")
            return

        status_color = _COLOR_GREEN if summary.failed == 0 else _COLOR_RED
        print(f"  {_COLOR_BOLD}{'=' * 50}{_COLOR_RESET}")
        print(f"  {_COLOR_BOLD}Results:{_COLOR_RESET}")
        print(f"    Total:  {summary.total}")
        print(f"    {_COLOR_GREEN}Passed: {summary.passed}{_COLOR_RESET}")
        if summary.failed:
            print(f"    {_COLOR_RED}Failed: {summary.failed}{_COLOR_RESET}")
        if summary.skipped:
            print(f"    {_COLOR_YELLOW}Skipped: {summary.skipped}{_COLOR_RESET}")
        if summary.error:
            print(f"    {_COLOR_RED}Error:  {summary.error}{_COLOR_RESET}")
        print(f"    Pass Rate: {status_color}{summary.pass_rate}%{_COLOR_RESET}")
        print(f"    Duration: {summary.duration:.1f}s")
        print(f"  {_COLOR_BOLD}{'=' * 50}{_COLOR_RESET}\n")

    @staticmethod
    def print_failure_detail(result: TestResult) -> None:
        if result.status not in ("failed", "error"):
            return
        print(f"\n{_COLOR_RED}--- {result.test_case.name} ---{_COLOR_RESET}")
        if result.error_traceback:
            print(result.error_traceback)
        elif result.error:
            print(f"{type(result.error).__name__}: {result.error}")
        if result.screenshots:
            print("Screenshots:")
            for s in result.screenshots:
                print(f"  - {s}")
