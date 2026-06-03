# 人工验收测试

这份清单用于确认 `ui-autoplat` 是否已经具备人工试用和验收条件。

先在项目根目录准备一个 `$repo` 变量，后续切换目录都使用它，避免 PowerShell 相对路径误跳：

```powershell
$repo = "D:\02Personal\Automation\ui_autoplat"
Set-Location $repo
```

## 1. 准备环境

以 editable 模式安装项目：

```powershell
pip install -e .[all]
```

安装 Chromium 浏览器二进制：

```powershell
autoplat browser-install
```

运行环境自检：

```powershell
autoplat doctor --config examples/page_object/autoplat.yaml
```

预期结果：

- 命令退出码为 `0`。
- Python、Robocorp Tasks、Robocorp Browser、Playwright、Pydantic、PyYAML、配置、发现路径、浏览器二进制检查均为 `OK`。

如果当前网络无法下载浏览器，可先跳过浏览器二进制检查：

```powershell
autoplat doctor --config examples/page_object/autoplat.yaml --skip-browser
```

## 2. 发现测试

```powershell
autoplat discover examples/page_object --format table
autoplat discover examples/data_driven --format json
```

预期结果：

- `examples/page_object` 能列出 `test_login_with_page_object`。
- `examples/data_driven` 能展开为数据驱动用例。
- 终端没有 import error。

## 3. 运行通过的浏览器示例

```powershell
Set-Location "$repo\examples\page_object"
autoplat config validate --config autoplat.yaml
autoplat run . --config autoplat.yaml --report all
```

预期结果：

- 命令退出码为 `0`。
- 1 个用例通过。
- 报告和历史记录生成在 `examples/page_object/output/` 下。
- `output/reports/log.html`, `output/reports/results.json`, and `output/reports/junit.xml` exist.

打开 HTML 报告：

```powershell
autoplat report --format html --output-dir output --open
```

人工检查：

- 报告能显示通过的用例。
- 链接没有指向不存在的文件。
- 顶部筛选按钮、搜索框、匹配数量可见。
- `Slowest tests` 区域能列出耗时最高的用例。

## 4. 运行数据驱动示例

```powershell
Set-Location "$repo\examples\data_driven"
autoplat config validate --config autoplat.yaml
autoplat run . --config autoplat.yaml --mode in-process --report json
```

预期结果：

- 命令退出码为 `0`。
- JSON 报告包含 `case_id`、`case_name`、`parameters` 和跳过行的元数据。
- 如果测试数据中标记了跳过，则至少有 1 个用例为 skipped。

查看 JSON 报告：

```powershell
Get-Content output\reports\results.json
```

## 5. 验证失败诊断产物

这个示例预期会失败，用来验证失败诊断链路。

```powershell
Set-Location "$repo\examples\browser_failure"
autoplat config validate --config autoplat.yaml
autoplat run . --config autoplat.yaml --report all
```

预期结果：

- 命令退出码为 `1`。
- `test_missing_heading` is failed.
- `output/reports/log.html`, `output/reports/results.json`, and `output/reports/junit.xml` exist.
- `output/artifacts/` 包含收集到的 Robocorp 产物。
- `output/artifacts/.../stdout.log` 和 `output/artifacts/.../stderr.log` 存在。
- 如果 Robocorp 在 `output.robolog` 中嵌入了截图，`output/screenshots/` 下会有 PNG 截图。

打开 HTML 报告：

```powershell
autoplat report --format html --output-dir output --open
```

人工检查：

- 失败用例和真实错误摘要可见，例如 Playwright timeout。
- 点击 `Failed` 筛选按钮后，只显示失败用例。
- 在搜索框输入 `missing_heading` 后，仍能筛选出失败用例。
- 输入不存在的关键字后，页面显示空结果提示。
- `Full traceback / raw output` 可以展开查看完整原始输出。
- `Screenshots` 区域展示截图缩略图，点击可以打开原图。
- `Primary logs`、`Raw process output`、`Other artifacts` 分组可见。
- `stdout.log`、`stderr.log`、`log.html`、`output.robolog` 链接可以打开。

后续 history 和 API 检查继续留在这个目录执行。

## 6. 检查历史记录

从带有 `output/history.db` 的目录执行，例如第 5 步之后的 `examples/browser_failure`。

```powershell
autoplat history --format table
autoplat history --format json
```

预期结果：

- 终端能打印最近运行统计。
- JSON 输出包含 `trend`、`flaky`、`recent` 和 `stats`。

## 7. 检查 API 服务

在同一个示例目录启动 API 服务：

```powershell
autoplat serve --host 127.0.0.1 --port 8080
```

在另一个终端请求接口。PowerShell 中请使用 `curl.exe`，不要使用 `curl` alias：

```powershell
curl.exe http://127.0.0.1:8080/
curl.exe http://127.0.0.1:8080/api/health
curl.exe http://127.0.0.1:8080/api/runs/status
curl.exe http://127.0.0.1:8080/api/config
curl.exe "http://127.0.0.1:8080/api/suites?suite_path=."
curl.exe http://127.0.0.1:8080/api/runs/latest
curl.exe "http://127.0.0.1:8080/api/stats?days=abc"
```

预期结果：

- `/` 列出可用 endpoint。
- `/api/health` 返回 `{"status": "ok", ...}`。
- `/api/runs/status` 返回当前运行状态，空闲时通常为 `idle`，异步运行时为 `running`。
- `/api/config` 返回有效配置。
- `/api/suites` 列出 `test_missing_heading`。
- `/api/runs/latest` 返回最近一次持久化运行，或者返回明确的 `No runs recorded yet` 信息。
- `/api/stats?days=abc` 返回 HTTP 400，并包含结构化错误：`error.code = invalid_parameter`。

可选异步触发运行：

```powershell
curl.exe -X POST http://127.0.0.1:8080/api/runs `
  -H "Content-Type: application/json" `
  -d "{\"suite_path\":\".\",\"async_run\":true}"
curl.exe http://127.0.0.1:8080/api/runs/status
curl.exe -X POST http://127.0.0.1:8080/api/runs/cancel
```

预期结果：

- POST 请求立即返回 `accepted: true`。
- 运行中再次触发运行会返回 HTTP 409，`error.code = run_already_in_progress`。
- 取消请求会设置 `cancel_requested: true`。
- 当前版本采用协作式取消：不会强制杀掉已经开始执行的用例、线程或浏览器进程，但会在用例之间停止后续执行，并将剩余用例标记为 skipped。

使用 `Ctrl+C` 停止服务。

## 需要记录的信息

人工测试时请记录：

- 操作系统和 Python 版本。
- `autoplat doctor` 是否能在不加 `--skip-browser` 的情况下通过。
- 失败命令的退出码和完整终端输出。
- HTML 报告链接是否能正常打开。
- 失败截图是否生成，缩略图是否能显示。
- CLI 输出或报告 UI 中任何不清楚、不顺手的地方。
