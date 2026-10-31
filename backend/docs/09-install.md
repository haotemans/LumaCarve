# 09 · 一键依赖安装（tools/setup.py）

对应代码：[tools/setup.py](../../tools/setup.py)；对应测试：`tests/test_installer.py`。

## Windows PowerShell

在仓库根目录执行：
```powershell
py -3.11 tools/setup.py --region cn --torch cu128 --attention auto
.\.venv\Scripts\python.exe -m uvicorn lumacarve_server.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

生成 **唯一** `LumaCarve/.venv`；不会另外创建 `backend/.venv`，前端也不需要 Python 虚拟环境。

`--torch cpu|cu126|cu128|cu130|default` 指定 PyTorch 官方 wheel 索引；应根据 GPU 驱动与 PyTorch 官方兼容矩阵选择，而不是仅凭安装了某个 CUDA Toolkit。用 `--profile api` 可以仅安装 FastAPI 等轻量依赖，适合无显卡开发。

## Linux / WSL2 CUDA

```bash
python3.11 tools/setup.py --torch cu128 --attention both
.venv/bin/python -m uvicorn lumacarve_server.app:app --app-dir backend --host 127.0.0.1 --port 8000
```

安装器：创建/复用根 `.venv` → 更新 pip 构建工具 → 安装 PyTorch → 安装 API / 推理 / 训练依赖 → 检查 `torch.cuda.is_available()` 和 `nvcc` → 按平台尝试 FlashAttention-2 / SageAttention。**若 FlashAttention 或 SageAttention 编译失败，默认保留可运行的 PyTorch SDPA**。可使用 `--strict-attention` 让失败直接退出。

- 默认 `--attention auto` 在 Linux CUDA Toolkit 可用时依次尝试两个库；在 Windows/CPU/无 nvcc 环境中跳过源码编译，保留 SDPA。
- `--attention none` 跳过两个第三方加速包；SDPA 已具备 GPU 融合注意力实现。
- `--profile api` 仅安装后端 API 和测试依赖，不安装 PyTorch。
- 安装报告保存于 `LumaCarveData/dependency-install.json`，它不会泄露到 Git。
- 尚不支持自动下载来路不明的 Windows 轮子，避免破坏用户 CUDA 环境。

**注意：** 依赖安装成功≠图像生成已实现；模型加载器与实际 attention dispatch 仍需要逐模型验证。

参考：[PyTorch 官方安装](https://pytorch.org/get-started/locally/)；[FlashAttention](https://github.com/Dao-AILab/flash-attention)；[SageAttention](https://github.com/thu-ml/SageAttention)。


## 国内专用源

`--region cn`：清华 TUNA PyPI、中国教育网 PyTorch CUDA wheel 镜像，以及 ModelScope 模型客户端下载组件；`--torch-source official` 仅对 PyTorch wheel 使用官方源。详情见 [11-download-sources.md](11-download-sources.md)、[12-modelscope-downloads.md](12-modelscope-downloads.md)。


## Rust 调度器安装策略

安装器新增 `--scheduler auto|required|python`。默认 `auto`：如果本机有 Cargo，会使用 maturin **在项目根 .venv 内构建并安装 PyO3 wheel**，并验证可以导入；如果没有 Rust 编译器或编译失败，使用现有 Python 图计划回退并写入安装报告。不会从来历不明的源下载二进制 wheel。

`--scheduler required` 要求 Rust 存在且能够成功构建，否则命令失败；`--scheduler python` 显式跳过。Windows 可以先通过 Rust 官方 rustup 安装编译工具，须确保 C++ Build Tools 等编译依赖齐备。Rust 编译不需要另一个 Python 虚拟环境。

这个选项使 Graph 编译优先 Rust，但 Python `JobQueue`、实际模型运行及 CUDA 同步尚未改为 Rust。细节见 [14-rust-graph-bridge.md](14-rust-graph-bridge.md)。
