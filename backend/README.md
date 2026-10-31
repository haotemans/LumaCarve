# LumaCarve · 后端模块目录

> 本阶段提供**可启动的本地 API 与可测试的调度基础**，不是已经能够生成图片或训练 LoRA 的完整后端。真实模型的 PyTorch/CUDA 适配器尚未连接；`POST /api/v1/jobs` 会明确返回 **503**，不会制造假图片、假 GPU 数值或假完成任务。

## 一键创建统一 .venv（Windows PowerShell）

在仓库根目录执行 `py -3.11 tools/setup.py --torch cu128 --attention auto`，安装报告位于 `LumaCarveData/dependency-install.json`。在 Windows 默认保留 PyTorch SDPA，不强制编译 FlashAttention/SageAttention；Linux + CUDA Toolkit 可以尝试两个包。详细见 [08-dependencies.md](docs/08-dependencies.md)、[09-install.md](docs/09-install.md)、[10-attention.md](docs/10-attention.md)。

## 中国大陆依赖与模型下载

```powershell
# 项目根目录：依赖使用清华 TUNA / CERNET PyTorch wheel 镜像
py -3.11 tools/setup.py --region cn --torch cu128 --attention auto
# 只有用户启用后才允许 API 下载模型（默认通过魔搭）
$env:LUMACARVE_DOWNLOAD_REGION="cn"
$env:LUMACARVE_ALLOW_MODEL_DOWNLOAD="1"
cd backend
..\.venv\Scripts\python.exe -m uvicorn lumacarve_server.app:app --host 127.0.0.1 --port 8000
```

再从本地 API 文档调用 `GET /api/v1/downloads/catalog` 和 `POST /api/v1/downloads`。已配置 Qwen-Image-2.1 和 MOSS-Image-Base；其他模型先核实仓库后才进入目录。下载具体细节与限制见 [11-download-sources.md](docs/11-download-sources.md)、[12-modelscope-downloads.md](docs/12-modelscope-downloads.md)。

## 快速启动（Windows PowerShell）

```powershell
cd LumaCarve\backend
..\.venv\Scripts\python.exe -m uvicorn lumacarve_server.app:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/docs` 查看可交互 API 文档。`http://127.0.0.1:8000/api/v1/health` 应返回 `status=ok`。

## 代码与文档一一对应

| 功能 | 代码 | 说明 | 测试 |
|---|---|---|---|
| 配置与数据目录 | `lumacarve_server/config.py` | [01-config.md](docs/01-config.md) | `test_server.py` |
| FastAPI 启动 | `lumacarve_server/app.py` | [02-app.md](docs/02-app.md) | `test_server.py` |
| Graph 工作流校验 | `lumacarve_server/workflows.py` + `routers/workflows.py` | [03-workflow.md](docs/03-workflow.md) | `test_workflows.py` |
| 模型索引 | `lumacarve_server/models.py` + `routers/models.py` | [04-model-registry.md](docs/04-model-registry.md) | `test_models.py` |
| 图片上传与读取 | `lumacarve_server/assets.py` + `routers/assets.py` | [05-assets.md](docs/05-assets.md) | `test_assets.py` |
| Rust/SQLite 调度桥接 | `lumacarve_runtime/queue_bridge.py` | [15-rust-queue-bridge.md](docs/15-rust-queue-bridge.md) | `test_queue_bridge.py` |
| 任务队列与历史 | `lumacarve_server/jobs.py` + `routers/jobs.py` | [06-job-queue.md](docs/06-job-queue.md) | `test_jobs.py` |
| Rust Graph 桥接 | `lumacarve_runtime/rust_bridge.py` | [14-rust-graph-bridge.md](docs/14-rust-graph-bridge.md) | `test_rust_bridge.py` |
| Python 包与路由打包 | `pyproject.toml` | [13-package-layout.md](docs/13-package-layout.md) | `test_packaging.py` |
| 一键环境安装 | `../tools/setup.py` + `pyproject.toml` | [08-dependencies.md](docs/08-dependencies.md), [09-install.md](docs/09-install.md) | `test_installer.py` |
| 国内/国际下载源 | `lumacarve_server/download_sources.py` + `tools/setup.py` | [11-download-sources.md](docs/11-download-sources.md) | `test_installer.py` |
| ModelScope 模型下载 | `lumacarve_server/model_downloads.py` + `routers/downloads.py` | [12-modelscope-downloads.md](docs/12-modelscope-downloads.md) | `test_downloads.py` |
| Flash/Sage/SDPA 决策 | `lumacarve_runtime/attention.py` | [10-attention.md](docs/10-attention.md) | `test_attention.py` |
| GPU/RAM/SSD 驻留策略 | `lumacarve_runtime/{graph,budget,residency,executor}.py` | [07-runtime.md](docs/07-runtime.md) | `test_runtime.py` |

## 测试

```powershell
cd LumaCarve\backend
py -m unittest discover -s tests -v
```

GitHub Actions 在 `.github/workflows/backend-ci.yml` 中执行 Python 3.11 测试；不需要 GPU。

## Rust 调度内核（元数据策略已实现，GPU 执行未接通）

Rust 代码位于 [`scheduler/`](../scheduler/README.md)。它包含 DAG 计划、节点缓存签名、单 GPU 优先级队列、内存预算租约和可选 PyO3 扩展。通过 maturin 安装到同一个 `.venv` 后，Python Graph 编译优先调用 Rust；没有扩展则使用 Python 实现。详细说明见 [14-rust-graph-bridge.md](docs/14-rust-graph-bridge.md)。

## 接口状态

- `GET /api/v1/health`：可用。仅表示本地 API 存活。
- `GET /api/v1/runtime`：可用。目前报告推理后端未连接。
- `GET /api/v1/models`：可用。只扫描受控目录的 `.safetensors` 文件，不证明模型能运行。
- `POST /api/v1/assets`、`GET /api/v1/assets/{id}`：可用。校验并存取 PNG/JPEG/WebP。
- `POST /api/v1/workflows/validate`：可用。校验前端 Graph JSON 结构、参数和类型。
- `GET /api/v1/jobs`、`GET /api/v1/jobs/{id}`、`POST /api/v1/jobs/{id}/cancel`：可用。持久化任务状态。
- `POST /api/v1/jobs`：API 可调用，但未配置真实推理适配器时返回 503。
- `GET /api/v1/downloads/catalog`：返回国内/国际模型仓库目录。
- `POST /api/v1/downloads`、`GET /api/v1/downloads/{id}`：显式启用后下载 ModelScope/Hugging Face 模型，查询下载状态；不自动载入 GPU。

## 接下来

1. **模型适配器**：验证 Qwen-Image-2.1 实际推理 API、模型子组件、加载精度与编辑能力；不依赖前端静态能力预设做运行时承诺。
2. **真实图像执行器**：用 Graph 编译结果进行文本编码、扩散、VAE 解码与图片保存，接入安全取消机制。
3. **LoRA Stack**：验证模型家族的可用 LoRA 格式，按兼容性与显存预算加载，支持多个 LoRA 共享基础模型。
4. **性能验证**：测量实际峰值 GPU 显存、系统内存、首张生成时间和连续生成速度后，才选择全量驻留、整组件卸载或量化。
5. **训练引擎**：独立实现可暂停/恢复的训练执行器，与生成队列共享 GPU 资源仲裁。

为了减小开销，API 导入阶段不加载 CUDA/PyTorch，设备检查也不在健康检查时执行。默认仅绑定 `127.0.0.1`，不要映射到公网。
