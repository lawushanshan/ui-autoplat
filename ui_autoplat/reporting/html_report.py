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
.test-list {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.test-item {{ padding: 12px 20px; border-bottom: 1px solid #eee; display: flex; align-items: center; justify-content: space-between; }}
.test-item:last-child {{ border-bottom: none; }}
.test-name {{ font-weight: 500; }}
.test-meta {{ font-size: 12px; color: #666; }}
.status-badge {{ padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; color: #fff; }}
.status-passed {{ background: #28a745; }}
.status-failed {{ background: #dc3545; }}
.status-skipped {{ background: #ffc107; color: #333; }}
.status-error {{ background: #dc3545; }}
.error-detail {{ background: #fff0f0; padding: 10px 20px; border-bottom: 1px solid #eee; font-family: monospace; font-size: 13px; white-space: pre-wrap; color: #c00; }}
.artifact-list {{ background: #fafafa; padding: 10px 20px 14px 20px; border-bottom: 1px solid #eee; font-size: 13px; }}
.artifact-list a {{ color: #2563eb; text-decoration: none; margin-right: 12px; }}
.artifact-list a:hover {{ text-decoration: underline; }}
.screenshot {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; margin-top: 8px; }}
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

<div class="test-list">
{test_items}
</div>

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
            item_html = (
                f'<div class="test-item">'
                f'<div>'
                f'<div class="test-name">{result.test_case.name}</div>'
                f'<div class="test-meta">'
                f'{result.test_case.suite_name} | {result.test_case.file_path.name}'
                f'{f" | Tags: {', '.join(result.test_case.tags)}" if result.test_case.tags else ""}'
                f'</div></div>'
                f'<div style="display:flex;align-items:center;gap:12px;">'
                f'<span style="font-size:13px">{result.duration:.1f}s</span>'
                f'<span class="status-badge {status_class}">{result.status.upper()}</span>'
                f'</div></div>'
            )

            if result.error_traceback:
                item_html += (
                    f'<div class="error-detail" id="{error_id}">'
                    f"{self._escape_html(result.error_traceback)}"
                    f'</div>'
                )
            elif result.error:
                item_html += (
                    f'<div class="error-detail" id="{error_id}">'
                    f"{self._escape_html(str(result.error))}"
                    f'</div>'
                )

            if result.screenshots or result.log_path or result.video_path or result.artifacts:
                links = []
                for screenshot in result.screenshots:
                    links.append(self._artifact_link("screenshot", screenshot))
                if result.log_path:
                    links.append(self._artifact_link("log", result.log_path))
                if result.video_path:
                    links.append(self._artifact_link("video", result.video_path))
                for artifact in result.artifacts:
                    if artifact in result.screenshots or artifact == result.log_path or artifact == result.video_path:
                        continue
                    links.append(self._artifact_link(artifact.name, artifact))
                item_html += f'<div class="artifact-list">Artifacts: {" ".join(links)}</div>'

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
            pass_rate=summary.pass_rate,
            duration=f"{summary.duration:.1f}",
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
