from __future__ import annotations

import os
from pathlib import Path

from ui_autoplat.config.settings import OutputConfig
from ui_autoplat.core.models import TestResult, TestRun


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Test Report - {run_id}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; color: #333; }}
.header {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 15px; margin-top: 15px; }}
.stat {{ text-align: center; padding: 10px; border-radius: 6px; background: #f8f9fa; }}
.stat-value {{ font-size: 24px; font-weight: bold; }}
.stat-label {{ font-size: 12px; color: #666; margin-top: 4px; }}
.pass {{ color: #28a745; }}
.fail {{ color: #dc3545; }}
.skip {{ color: #ffc107; }}
.error {{ color: #dc3545; }}
.toolbar {{ background: #fff; border-radius: 8px; padding: 12px 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
.filter-buttons {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.filter-button {{ border: 1px solid #d0d7de; background: #fff; border-radius: 6px; padding: 6px 10px; cursor: pointer; font-size: 13px; color: #333; }}
.filter-button.active {{ background: #1f6feb; border-color: #1f6feb; color: #fff; }}
.search-input {{ min-width: 240px; flex: 1; max-width: 420px; border: 1px solid #d0d7de; border-radius: 6px; padding: 7px 10px; font-size: 13px; }}
.match-count {{ font-size: 13px; color: #666; margin-left: auto; }}
.slow-section {{ background: #fff; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.section-title {{ font-size: 15px; font-weight: 600; margin-bottom: 10px; }}
.slow-list {{ display: grid; gap: 6px; }}
.slow-item {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: center; font-size: 13px; padding: 6px 0; border-top: 1px solid #eee; }}
.slow-name {{ overflow-wrap: anywhere; }}
.slow-duration {{ font-family: monospace; color: #555; }}
.empty-state {{ background: #fff; border-radius: 8px; padding: 18px; color: #666; text-align: center; display: none; }}
.test-list {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.test-entry[hidden] {{ display: none; }}
.test-item {{ padding: 12px 20px; border-bottom: 1px solid #eee; display: flex; align-items: center; justify-content: space-between; }}
.test-item:last-child {{ border-bottom: none; }}
.test-name {{ font-weight: 500; }}
.test-meta {{ font-size: 12px; color: #666; }}
.status-badge {{ padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #fff; }}
.status-passed {{ background: #28a745; }}
.status-failed {{ background: #dc3545; }}
.status-skipped {{ background: #ffc107; color: #333; }}
.status-error {{ background: #dc3545; }}
.error-summary {{ background: #fff0f0; padding: 10px 20px; border-bottom: 1px solid #eee; font-family: monospace; font-size: 13px; white-space: pre-wrap; color: #c00; }}
.traceback-detail {{ background: #fff; border-bottom: 1px solid #eee; padding: 10px 20px; }}
.traceback-detail summary {{ cursor: pointer; color: #555; font-size: 13px; }}
.traceback-detail pre {{ overflow-x: auto; white-space: pre-wrap; font-size: 12px; line-height: 1.45; color: #444; background: #f8f9fa; padding: 10px; border-radius: 4px; }}
.diagnostics {{ background: #fafafa; padding: 12px 20px 16px 20px; border-bottom: 1px solid #eee; font-size: 13px; }}
.diagnostic-group {{ margin-top: 10px; }}
.diagnostic-title {{ font-weight: 600; color: #444; margin-bottom: 6px; }}
.diagnostic-links a {{ color: #2563eb; text-decoration: none; margin-right: 12px; display: inline-block; margin-bottom: 4px; }}
.diagnostic-links a:hover {{ text-decoration: underline; }}
.screenshot-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 240px)); gap: 12px; }}
.screenshot-card {{ display: block; color: #2563eb; text-decoration: none; }}
.screenshot-card img {{ width: 100%; max-height: 160px; object-fit: contain; border: 1px solid #ddd; border-radius: 4px; background: #fff; }}
.screenshot-card span {{ display: block; margin-top: 4px; overflow-wrap: anywhere; }}
.env-info {{ margin-top: 10px; font-size: 12px; color: #666; }}
</style>
</head>
<body>

<div class="header">
<h1>Test Report</h1>
<div class="env-info">Run ID: {run_id} | {timestamp} | Browser: {browser} | Python: {python_version}</div>
<div class="summary">
<div class="stat"><div class="stat-value">{total}</div><div class="stat-label">Total</div></div>
<div class="stat"><div class="stat-value pass">{passed}</div><div class="stat-label">Passed</div></div>
<div class="stat"><div class="stat-value fail">{failed}</div><div class="stat-label">Failed</div></div>
<div class="stat"><div class="stat-value skip">{skipped}</div><div class="stat-label">Skipped</div></div>
<div class="stat"><div class="stat-value">{pass_rate}%</div><div class="stat-label">Pass Rate</div></div>
<div class="stat"><div class="stat-value">{duration}s</div><div class="stat-label">Duration</div></div>
</div>
</div>

<div class="toolbar">
<div class="filter-buttons" aria-label="Status filters">
<button class="filter-button active" type="button" data-filter="all">All ({total})</button>
<button class="filter-button" type="button" data-filter="passed">Passed ({passed})</button>
<button class="filter-button" type="button" data-filter="failed">Failed ({failed})</button>
<button class="filter-button" type="button" data-filter="skipped">Skipped ({skipped})</button>
<button class="filter-button" type="button" data-filter="error">Error ({error})</button>
</div>
<input id="test-search" class="search-input" type="search" placeholder="Search by test, suite, tag, or file">
<div id="match-count" class="match-count">{total} shown</div>
</div>

{slow_section}

<div class="test-list">
{test_items}
</div>
<div id="empty-state" class="empty-state">No tests match the current filters.</div>

<script>
(function () {{
  var currentFilter = "all";
  var buttons = Array.prototype.slice.call(document.querySelectorAll(".filter-button"));
  var search = document.getElementById("test-search");
  var entries = Array.prototype.slice.call(document.querySelectorAll(".test-entry"));
  var matchCount = document.getElementById("match-count");
  var emptyState = document.getElementById("empty-state");

  function applyFilters() {{
    var query = (search.value || "").trim().toLowerCase();
    var visible = 0;

    entries.forEach(function (entry) {{
      var status = entry.getAttribute("data-status");
      var searchText = entry.getAttribute("data-search") || "";
      var statusMatched = currentFilter === "all" || status === currentFilter;
      var searchMatched = !query || searchText.indexOf(query) !== -1;
      var show = statusMatched && searchMatched;
      entry.hidden = !show;
      if (show) {{
        visible += 1;
      }}
    }});

    matchCount.textContent = visible + " shown";
    emptyState.style.display = visible === 0 ? "block" : "none";
  }}

  buttons.forEach(function (button) {{
    button.addEventListener("click", function () {{
      currentFilter = button.getAttribute("data-filter");
      buttons.forEach(function (item) {{ item.classList.remove("active"); }});
      button.classList.add("active");
      applyFilters();
    }});
  }});

  search.addEventListener("input", applyFilters);
}})();
</script>

</body>
</html>
"""


class HTMLReportGenerator:
    def __init__(self, output_config: OutputConfig) -> None:
        self._output_dir = output_config.dir / "reports"

    def generate(self, run: TestRun) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)

        summary = run.summary
        env = run.environment or {}

        test_items_html = []
        for result in run.results:
            status_class = f"status-{result.status}"
            error_id = f"error-{result.test_case.name}"
            meta_parts = [result.test_case.suite_name, result.test_case.file_path.name]
            case_label = result.test_case.case_id or result.test_case.case_name
            if case_label:
                meta_parts.append(f"Case: {case_label}")
            if result.test_case.tags:
                meta_parts.append(f"Tags: {', '.join(result.test_case.tags)}")
            search_text = " ".join(
                [
                    result.test_case.name,
                    result.test_case.suite_name,
                    result.test_case.file_path.name,
                    " ".join(result.test_case.tags),
                    result.test_case.case_id or "",
                    result.test_case.case_name or "",
                    result.status,
                ]
            ).lower()
            item_html = (
                f'<div class="test-entry" data-status="{result.status}" '
                f'data-search="{self._escape_html(search_text)}">'
                f'<div class="test-item">'
                f'<div>'
                f'<div class="test-name">{result.test_case.name}</div>'
                f'<div class="test-meta">'
                f'{self._escape_html(" | ".join(meta_parts))}'
                f'</div></div>'
                f'<div style="display:flex;align-items:center;gap:12px;">'
                f'<span style="font-size:13px">{result.duration:.1f}s</span>'
                f'<span class="status-badge {status_class}">{result.status.upper()}</span>'
                f'</div></div>'
            )

            if result.error:
                item_html += (
                    f'<div class="error-summary" id="{error_id}">'
                    f"{self._escape_html(str(result.error))}"
                    f'</div>'
                )
            if result.error_traceback:
                item_html += (
                    f'<details class="traceback-detail">'
                    f'<summary>Full traceback / raw output</summary>'
                    f'<pre>{self._escape_html(result.error_traceback)}</pre>'
                    f'</details>'
                )

            if result.screenshots or result.log_path or result.video_path or result.artifacts:
                item_html += self._diagnostics_html(result)

            item_html += "</div>"
            test_items_html.append(item_html)

        html = HTML_TEMPLATE.format(
            run_id=run.id,
            timestamp=run.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            browser=getattr(env, "browser_type", "unknown"),
            python_version=getattr(env, "python_version", "unknown"),
            total=summary.total,
            passed=summary.passed,
            failed=summary.failed,
            skipped=summary.skipped,
            error=summary.error,
            pass_rate=summary.pass_rate,
            duration=f"{summary.duration:.1f}",
            slow_section=self._slow_section_html(run.results),
            test_items="\n".join(test_items_html),
        )

        report_path = self._output_dir / "log.html"
        report_path.write_text(html, encoding="utf-8")
        return report_path

    @staticmethod
    def _escape_html(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _artifact_link(self, label: str, path: Path) -> str:
        try:
            href = os.path.relpath(path, self._output_dir)
        except ValueError:
            href = str(path)
        href = self._escape_html(href.replace("\\", "/"))
        return f'<a href="{href}">{self._escape_html(label)}</a>'

    def _diagnostics_html(self, result: TestResult) -> str:
        groups = []

        if result.screenshots:
            cards = []
            for screenshot in result.screenshots:
                href = self._artifact_href(screenshot)
                label = self._escape_html(screenshot.name)
                cards.append(
                    f'<a class="screenshot-card" href="{href}">'
                    f'<img src="{href}" alt="{label}">'
                    f'<span>{label}</span>'
                    f'</a>'
                )
            groups.append(self._diagnostic_group("Screenshots", '<div class="screenshot-grid">' + "".join(cards) + "</div>"))

        primary_links = []
        if result.log_path:
            primary_links.append(self._artifact_link("Robocorp log", result.log_path))
        if result.video_path:
            primary_links.append(self._artifact_link("Video", result.video_path))
        if primary_links:
            groups.append(self._diagnostic_group("Primary logs", self._link_group(primary_links)))

        stdout_stderr = []
        other_artifacts = []
        seen = set(result.screenshots)
        if result.log_path:
            seen.add(result.log_path)
        if result.video_path:
            seen.add(result.video_path)

        for artifact in result.artifacts:
            if artifact in seen:
                continue
            if artifact.name in {"stdout.log", "stderr.log"}:
                stdout_stderr.append(self._artifact_link(artifact.name, artifact))
            else:
                other_artifacts.append(self._artifact_link(artifact.name, artifact))

        if stdout_stderr:
            groups.append(self._diagnostic_group("Raw process output", self._link_group(stdout_stderr)))
        if other_artifacts:
            groups.append(self._diagnostic_group("Other artifacts", self._link_group(other_artifacts)))

        return '<div class="diagnostics">' + "".join(groups) + "</div>"

    def _artifact_href(self, path: Path) -> str:
        try:
            href = os.path.relpath(path, self._output_dir)
        except ValueError:
            href = str(path)
        return self._escape_html(href.replace("\\", "/"))

    @staticmethod
    def _diagnostic_group(title: str, body: str) -> str:
        return f'<div class="diagnostic-group"><div class="diagnostic-title">{title}</div>{body}</div>'

    @staticmethod
    def _link_group(links: list[str]) -> str:
        return '<div class="diagnostic-links">' + " ".join(links) + "</div>"

    def _slow_section_html(self, results: list[TestResult]) -> str:
        slow_results = sorted(results, key=lambda result: result.duration, reverse=True)[:5]
        if not slow_results:
            return ""

        items = []
        for result in slow_results:
            label = self._escape_html(f"{result.test_case.suite_name} / {result.test_case.name}")
            items.append(
                '<div class="slow-item">'
                f'<div class="slow-name">{label}</div>'
                f'<div class="slow-duration">{result.duration:.2f}s</div>'
                '</div>'
            )

        return (
            '<div class="slow-section">'
            '<div class="section-title">Slowest tests</div>'
            '<div class="slow-list">'
            + "".join(items)
            + '</div></div>'
        )
