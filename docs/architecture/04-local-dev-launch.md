# 04 · 单目录本地开发启动

整个项目放在一个目录，Python / 前端依赖 / 模型与用户数据不会默认分散到不同盘符。

## 目录

- `<repo>/.venv/`：唯一 Python 环境。
- `<repo>/frontend/node_modules/`：Vue/npm 依赖。
- `<repo>/LumaCarveData/`：用户模型、图片、数据集和 SQLite；后端运行时也使用此路径。

## Windows PowerShell

首次安装 Python 环境使用仓库已有 `tools/setup.py`，然后：

```powershell
cd frontend
npm.cmd install
cd ..
.\tools\start-dev.ps1
```

使用 `npm.cmd` 而不是 `npm`，避免 PowerShell 直接加载 `npm.ps1` 时触发 ExecutionPolicy 限制。脚本同时启动绑定 `127.0.0.1:8000` 的 FastAPI 和本地 Vue `127.0.0.1:5173`；在前端任务结束后退出后端进程。

## Linux

```bash
cd frontend && npm install && cd ..
./tools/start-dev.sh
```

默认 **不启动 GPU 推理**，只有用户显式设置 `LUMACARVE_INFERENCE_BACKEND=anima` 并安装完整模型/依赖，才允许真实 Anima 生图。脚本不自动下载模型、修改系统 PATH 或启动 Triton Benchmark。
