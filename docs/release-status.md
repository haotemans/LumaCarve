# LumaCarve 发行与功能状态

> 数据来源：`docs/release-status.json`。此页和 JSON 必须在每个影响交付范围的 PR 中同步维护。CI 会检查版本、发布资产名称、状态及证据文件是否一致。

核验日期：2026-11-07 · 仓库源码版本：`0.2.3`。平台发行版本**可能不同**，不能用 Windows 版本号推断 Linux 已经更新。

## 最新公开便携包

| 平台 | 发行版本 | 下载 | 对应提交 |
|---|---|---|---|
| Windows x64 | [v0.2.3-portable-preview.1](https://github.com/haotemans/LumaCarve/releases/tag/v0.2.3-portable-preview.1) | [LumaCarve-Windows-x64-Portable.zip](https://github.com/haotemans/LumaCarve/releases/download/v0.2.3-portable-preview.1/LumaCarve-Windows-x64-Portable.zip) · `SHA256SUMS-Windows.txt` | `22da0df5` |
| Linux x64 | [v0.2.2-portable-preview.1](https://github.com/haotemans/LumaCarve/releases/tag/v0.2.2-portable-preview.1) | [LumaCarve_0.2.2_amd64.AppImage](https://github.com/haotemans/LumaCarve/releases/download/v0.2.2-portable-preview.1/LumaCarve_0.2.2_amd64.AppImage) · `SHA256SUMS.txt` | `32ec7514` |

仅列出**已经上传 GitHub Releases 的真实资产**，不把 CI 测试产物、未构建的 ZIP 或历史安装器称为当前发行版。

## 已实现与未实现能力

| 功能 | 状态 | 验证边界 |
|---|---|---|
| Tauri 2 / Vue 3 窗口 | CI 已验证 | Windows 启动测试通过，仍需真实设备验收 |
| FastAPI / SQLite 本地服务 | CI 已验证 | Windows 打包 Sidecar 的鉴权健康检查通过 |
| Anima 生成适配器 | 代码已接入，GPU 未验证 | 仅有代码和模拟测试，未验证实际 GPU 出图 |
| 便携版 GPU 推理运行时 | 未打包 | 预览包没有 PyTorch / CUDA / GPU Worker / 模型权重 |
| LoRA 训练 Worker | 未实现 | 目前仅有配置/UI 草稿，不能实际训练 |
| Qwen 图像编辑 | 未实现 | 没有可执行的模型编辑适配器 |

**重要：本地 API 连接成功并不等于 GPU 推理可以使用。当前公开便携包不能完成 Anima 出图或 LoRA 训练。**

## 更新规则

1. 每个功能 PR 同步源码、模块 Markdown、测试和 `project-layout.toml`；若功能尚未完整验证，保留明确的限制。
2. 每次提升桌面版本同步更改 Vue `package.json`、Rust `Cargo.toml`、Tauri `tauri.conf.json` 及发布状态 JSON。
3. Windows 使用 Windows Runner 构建 ZIP，Linux 使用 Ubuntu Runner 构建 AppImage；两平台分别运行对应检查。
4. 只有发布成功并核对真实资产和提交 SHA 后，才在此更新最新版本；禁止覆盖历史 Release、上传安装包冒充便携版。
5. CI 自动运行 `python tools/check_release_status.py` 和对应回归测试；未通过不得合并。

参考：[构建与发行流程](ci-build.md) · [源码与模块文档](../project-layout.toml)。
