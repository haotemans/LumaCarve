# LumaCarve · 后端模块目录

> 本阶段提供**可启动的本地 API 与可测试的调度基础**，不是已经能够生成图片或训练 LoRA 的完整后端。真实模型的 PyTorch/CUDA 适配器尚未连接；`POST /api/v1/jobs` 会明确返回 **503**，不会制造假图片、假 GPU 数值或假完成任务。

## 快速启动（Windows PowerShell）

```powershell
cd LumaCarve\backend
py -m pip install -e ".[dev]"
py -m uvicorn lumacarve_server.app:app --host 127.0.0.1 --port 8000
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
| 任务队列与历史 | `lumacarve_server/jobs.py` + `routers/jobs.py` | [06-job-queue.md](docs/06-job-queue.md) | `test_jobs.py` |
| GPU/RAM/SSD 驻留策略 | `lumacarve_runtime/{graph,budget,residency,executor}.py` | [07-runtime.md](docs/07-runtime.md) | `test_runtime.py` |

## 测试

```powershell
cd LumaCarve\backend
py -m unittest discover -s tests -v
```

GitHub Actions 在 `.github/workflows/backend-ci.yml` 中执行 Python 3.11 测试；不需要 GPU。

## 接口状态

- `GET /api/v1/health`：可用。仅表示本地 API 存活。
- `GET /api/v1/runtime`：可用。目前报告推理后端未连接。
- `GET /api/v1/models`：可用。只扫描受控目录的 `.safetensors` 文件，不证明模型能运行。
- `POST /api/v1/assets`、`GET /api/v1/assets/{id}`：可用。校验并存取 PNG/JPEG/WebP。
- `POST /api/v1/workflows/validate`：可用。校验前端 Graph JSON 结构、参数和类型。
- `GET /api/v1/jobs`、`GET /api/v1/jobs/{id}`、`POST /api/v1/jobs/{id}/cancel`：可用。持久化任务状态。
- `POST /api/v1/jobs`：API 可调用，但未配置真实推理适配器时返回 503。

## 接下来

1. **模型适配器**：验证 Qwen-Image-2.1 实际推理 API、模型子组件、加载精度与编辑能力；不依赖前端静态能力预设做运行时承诺。
2. **真实图像执行器**：用 Graph 编译结果进行文本编码、扩散、VAE 解码与图片保存，接入安全取消机制。
3. **LoRA Stack**：验证模型家族的可用 LoRA 格式，按兼容性与显存预算加载，支持多个 LoRA 共享基础模型。
4. **性能验证**：测量实际峰值 GPU 显存、系统内存、首张生成时间和连续生成速度后，才选择全量驻留、整组件卸载或量化。
5. **训练引擎**：独立实现可暂停/恢复的训练执行器，与生成队列共享 GPU 资源仲裁。

为了减小开销，API 导入阶段不加载 CUDA/PyTorch，设备检查也不在健康检查时执行。默认仅绑定 `127.0.0.1`，不要映射到公网。
