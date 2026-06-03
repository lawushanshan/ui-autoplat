# CI/CD 集成指南

这份文档说明如何在流水线中运行 `ui-autoplat`，并收集报告、截图和失败诊断产物。

## 推荐流水线步骤

推荐顺序如下：

1. 检出代码。
2. 安装 Python 3.10 或更高版本。
3. 安装项目依赖。
4. 安装 Chromium 浏览器二进制。
5. 运行 `autoplat doctor` 做环境自检。
6. 运行自动化测试并输出 `all` 或至少 `junit` 报告。
7. 无论测试是否失败，都上传 `output/` 目录作为 artifact。
8. 将 `output/reports/junit.xml` 交给 CI 系统解析。

## 安装命令

```powershell
pip install -e .[all]
autoplat browser-install
```

如果 CI 环境不需要 Allure，可使用基础安装：

```powershell
pip install -e .
autoplat browser-install
```

## 环境自检

```powershell
autoplat doctor --config examples/page_object/autoplat.yaml
```

建议在 CI 中保留这一步。它可以提前暴露 Python 版本、关键依赖、配置、发现路径、浏览器二进制缺失等问题。

如果 CI 镜像已经预装浏览器，但路径检测不稳定，可临时使用：

```powershell
autoplat doctor --config examples/page_object/autoplat.yaml --skip-browser
```

## 运行测试

示例：

```powershell
autoplat run examples/page_object --config examples/page_object/autoplat.yaml --report all
```

如果只需要 CI 解析结果，至少生成 JUnit：

```powershell
autoplat run examples/page_object --config examples/page_object/autoplat.yaml --report junit
```

## 退出码约定

`autoplat run` 的退出码用于让 CI 正确判定流水线状态：

- `0`：测试执行完成且没有 failed/error。
- `1`：存在 failed/error，或者发现路径/配置等运行前置条件失败。

如果测试失败，命令会返回 `1`。CI 步骤通常会被标记为失败，但仍应上传 `output/` artifact，便于查看 HTML 报告、截图和原始日志。

## 推荐收集的产物

默认输出目录是 `output/`。常用产物：

| 路径 | 用途 |
| --- | --- |
| `output/reports/log.html` | 人工查看的 HTML 报告 |
| `output/reports/results.json` | 机器读取的结构化结果 |
| `output/reports/junit.xml` | CI 测试结果解析 |
| `output/screenshots/` | 失败截图 |
| `output/artifacts/` | Robocorp 日志、`stdout.log`、`stderr.log`、`output.robolog` |
| `output/history.db` | 本地历史记录 |
| `output/allure-results/` | Allure 结果目录 |

## GitHub Actions 示例

仓库中提供了示例工作流：

```text
.github/workflows/autoplat.yml
```

该示例包含：

- Python 版本设置。
- 依赖安装。
- Chromium 安装。
- `autoplat doctor` 环境自检。
- 平台单元测试。
- 示例 UI 自动化运行。
- JUnit 结果发布入口。
- `output/` artifact 上传。

如果你的测试项目不是 `examples/page_object`，需要调整 workflow 中的 `autoplat run` 路径和 `--config` 路径。

## 失败排查建议

优先查看：

1. CI 控制台中的 `autoplat doctor` 输出。
2. `output/reports/log.html` 中的失败摘要、截图和 artifact 分组。
3. `output/artifacts/.../stdout.log` 和 `stderr.log`。
4. `output/artifacts/.../log.html` 和 `output.robolog`。
5. `output/reports/junit.xml` 是否被 CI 正确识别。

如果浏览器启动失败，先确认：

- `autoplat browser-install` 是否成功。
- CI 环境是否允许启动 headless Chromium。
- 是否缺少系统级图形/字体/证书依赖。

## 并行执行

subprocess 模式支持 `--parallel`：

```powershell
autoplat run tests --config autoplat.yaml --mode subprocess --parallel 4 --report all
```

注意：

- 数据驱动用例当前需要 `in-process` 模式。
- `--stop-on-failure` 与并行执行不适合同时使用。
- 并行数应根据 CI runner CPU 和目标系统承载能力设置。
