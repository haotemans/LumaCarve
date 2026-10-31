# LumaCarve · 琢影

**A modular, local-first studio for image generation, image editing and LoRA training.**

> **Project status:** Frontend preview and a local FastAPI backend (graph validation, model discovery, image assets, SQLite job ledger, scheduling foundation) exist. Actual PyTorch/CUDA inference and LoRA training are NOT wired up or benchmarked.

LumaCarve（琢影）是一款面向本地 GPU 的模块化 LoRA 训练与图像创作、编辑工具，强调可控的训练流程、透明的资源占用、灵活的模型管理，以及适用于不同显存配置的优化策略。

## Architecture and technology stack

LumaCarve is a **modular monorepo**, not a collection of services. Source files, user model weights, and runtime artifacts have separate ownership:

- [Architecture overview](docs/architecture/README.md) · [Repository folders](docs/architecture/01-repository-layout.md)
- [Technology stack and decisions](docs/architecture/02-tech-stack.md) · [User data and cache layout](docs/architecture/03-data-layout.md)
- [ADR-0001: Modular monorepo](docs/architecture/ADR-0001-modular-monorepo.md)
- [Module → Markdown → Test manifest](project-layout.toml) · [Image Studio feature](frontend/src/features/image-studio/README.md)
- [Backend module guide](backend/README.md)

Existing Graph/parameter UI files now reside together in `frontend/src/features/image-studio/`. The global layout checker requires registered backend and Image Studio source files to have documentation and verification paths. Some older frontend pages remain in `frontend/src/pages/` and will be migrated gradually.

Technical choices: **React + TypeScript + Vite + React Flow** (UI); **Python 3.11+ + FastAPI + Pydantic** (local API); **SQLite + filesystem** (jobs/assets); **PyTorch + Diffusers + model-specific adapters** (planned inference/training), with optional FlashAttention/SageAttention and SDPA fallback. Heavy model loading is intentionally absent from API startup.

## Anima Base 1.0 · first inference integration

**Anima Base 1.0 is the first backend model family implemented.** Its optional Diffusers ModularPipeline adapter runs from verified local files through PyTorch/CUDA, uses the shared Rust-informed SQLite job queue, supports a LoRA Stack, and returns PNG outputs via `GET /api/v1/outputs/{output_id}`. The Image Studio now submits, polls and displays real results rather than pretending a model ran. These are code and CPU-mock-tested integration paths; **no actual GPU inference benchmark has been completed**.

- [Anima inference adapter](backend/docs/17-anima-adapter.md)
- [ModelScope / Hugging Face source compatibility](backend/docs/12-modelscope-downloads.md)
- [Real GPU smoke-test CLI](backend/docs/19-anima-smoke.md)
- [Image Studio API](frontend/src/features/image-studio/docs/api.md)

Anima's official ModelScope repo stores ComfyUI split weights, while the current runnable adapter expects the separate Hugging Face **Diffusers modular** snapshot. Select the `huggingface` provider when downloading Anima for this adapter. Split-weight loading from ModelScope is **not implemented yet**.

## Planned model support

- **Qwen-Image-2.1**（统一生成、图像编辑、多图参考、局部编辑和原生 RGBA，能力以官方文档与适配器验证为准）
- **MOSS-Image**
- **Anima Base 1.0 2B**
- **Krea 2 RAW**（非 Turbo）

每个模型系列将采用专门的模型适配器；组件结构、权重格式及加载限制须逐一验证。

## ComfyUI-inspired Rust scheduling core

Graph scheduling and cache-policy metadata now have an independent Rust crate in [scheduler/](scheduler/README.md), plus an optional [PyO3 bridge](backend/docs/14-rust-graph-bridge.md) installed into the same root `.venv`. Design references: [ADR-0002](docs/architecture/ADR-0002-rust-scheduler-comfyui-reference.md). We reference ComfyUI's architecture patterns (lazy dependencies, cache signatures, resource decisions) but do not copy GPL code. Python's SQLite queue now uses Rust's stateless task-choice policy when installed, with a tested Python fallback. **Real GPU execution, CUDA synchronization and Tensor cache eviction are still Python adapter work**, not completed Rust acceleration.

## Core design goals

### Training and precision

- 将 **Diffusion Transformer（扩散 Transformer 主模型）** 的 LoRA 训练作为主要 GPU 工作负载。
- 训练计算精度默认 **BF16**；视设备和后端支持提供 **FP16** 等选项。
- 模型加载精度目标支持 **INT8 / FP8 / BF16 / FP16**，按组件独立配置，并对不兼容组合给出明确错误提示。
- 面向 **8 GB / 16 GB / 24 GB** GPU 设计低显存预设；实际能否训练取决于模型、分辨率、优化器及硬件，尚待实测。

### Text Encoder（文本编码器）

- 默认冻结、不参与训练。
- 保留完整 Caption 的编码缓存，复用相同文本的编码结果。
- 探索在 CPU 上动态编码变化后的 Caption，并使用有限的异步预取队列，尽量避免 Text Encoder 占用训练 GPU 显存。
- CPU 编译与低比特加载属于可选、需实测的优化路径，不假定一定比普通 CPU 推理更快。

### Variational Autoencoder（变分自编码器）

- 在训练前确认分桶尺寸及静态图像预处理方案。
- 全量预编码训练图像的 Latent，并持久化到项目本地磁盘。
- 缓存完成后从训练 GPU 卸载 Variational Autoencoder；验证采样时按需加载解码。
- 缓存键与模型版本、裁剪和预处理参数绑定，避免复用不兼容结果。

### Caption dropout

- 提供 **Kohya 兼容模式**，准确区分整条 Caption Dropout 与 Tag Dropout。
- 提供与特殊学习率预设联动的实验性 **自然语言句子级 Dropout**。
- 特殊学习率预设：**Warmup 5% → Constant 10% → Cosine 85%**；前两阶段 Dropout 为 0，Cosine 阶段按余弦曲线逐渐增长至上限 5%。
- 支持用户手动提供需要保护的触发词。自然语言句子的可安全删除范围及策略仍在设计中，不会通过简单随机删除句子破坏核心语义。
- 训练器不重复调用外部图像描述 API；可复用数据集管理工具提供的 Caption 和先验元数据。

### Data pipeline

- 适配图片与同名文本 Caption（如一图一 `.txt`），并支持导入数据集管理工具导出的训练数据。
- 预览分桶、处理前后图像、Token 数和各桶分布；稀疏桶合并必须经过用户确认。
- 基于**完整图像 Token** 预算规划批次，避免截断图片 Token；确保每个 Epoch 的样本覆盖和重复次数行为可解释。

### Training workflow

- 支持多个优化器方案：AdamW、AdamW 8-bit、Muon、CAME、Automagic（实际兼容性逐项验证）。
- 训练界面采用三栏布局：参数配置、训练监控、逐 Epoch 采样画廊。
- 每 Epoch 自动保存 Checkpoint 与固定提示词采样；支持暂停、继续、停止、手动采样和立即保存。
- 监控 Loss、学习率、最大梯度，以及 GPU 显存、功耗和训练各环节耗时。

### Studio experience

规划页面：**监控仪表盘、LoRA 训练、图像工作室、出图管理、数据集查看、模型管理、任务历史、设置**。

**图像工作室**同时展示文字生成、参考图片编辑、局部重绘。React Flow 的 Graph 节点定义流程，参数模式只展示显式暴露的必要参数；同一个 LoRA Stack 节点支持 0—N 个 LoRA。**Anima 文字生图已连接真实 FastAPI 任务与结果 API**；其它模型的生成与图像编辑仍未接入，前端有明确标注的示例素材。

Qwen-Image-2.1 已有官方模型权重与多图编辑能力说明，但 LumaCarve 的模型适配器尚未实现。

模型文件可以从项目内目录或系统路径选择；缺失且未指定路径时，计划提供从 ModelScope（魔搭）或 Hugging Face 的首次自动下载。下载必须校验模型版本、许可与文件完整性。

## Current runtime foundation (implemented)

The `backend/lumacarve_runtime` Python package provides a device-independent runtime skeleton:

- `ExecutionPlanner` (`compile_workflow`): validates the Graph and computes dependency ordering and output lifetimes. The Graph defines execution flow; parameter mode is only a lightweight view of explicitly exposed settings.
- `MemoryBudgetController` (`MemoryBudget` / `preflight`): checks estimated simultaneous component-weight sizes with reserved headroom. This is **not** a measured CUDA peak-memory predictor.
- `ModelResidencyManager`: hot GPU / warm CPU / cold unloaded state accounting, LRU eviction, shared-instance leasing and protection against unloading active components.
- `run_plan`: executes a compiled plan through a user-provided callback, releasing dead intermediate results.
- Multiple LoRA identities can share one base-model component without an artificial item-count limit; available memory and model compatibility still constrain how many can be active.

Runtime unit tests (no GPU or PyTorch required):

```bash
cd backend
python -m unittest discover -s tests -v
```

**Not yet benchmarked:** actual Anima GPU inference (including real LoRA execution), memory telemetry, asynchronous transfers, Rust GPU scheduling, LoRA training, 8/16/24GB performance and other model adapters. Anima adapter code and its UI/API/PNG path now exist; the generic runtime residency manager is not yet directly driving the Anima ModularPipeline. See [backend/README.md](backend/README.md).

## China / Global download routes

Chinese users can install dependencies from regional PyPI + CUDA wheel mirrors and download full model snapshots from ModelScope. International mode uses official PyPI/PyTorch and Hugging Face. Both share the same root `.venv`. Explicitly choose `--region cn` to avoid ambiguous locale detection:

```powershell
py -3.11 tools/setup.py --region cn --torch cu128 --attention auto
```

Model download is opt-in; set `LUMACARVE_ALLOW_MODEL_DOWNLOAD=1` and `LUMACARVE_DOWNLOAD_REGION=cn` to use the local `/api/v1/downloads` endpoint. See [source selection](backend/docs/11-download-sources.md) and [ModelScope download guide](backend/docs/12-modelscope-downloads.md). Downloading a model does not mean inference adapters are ready.

## Unified Python environment and attention

The Python backend, model loaders and training tools share one repository-root `.venv`. To install on Windows, run `py -3.11 tools/setup.py --torch cu128 --attention auto` from the root (choose a compatible official PyTorch wheel for your GPU). Linux with CUDA Toolkit may attempt both FlashAttention and SageAttention; unsupported builds fall back to PyTorch SDPA. Each installation writes a local dependency report. See [backend/docs/09-install.md](backend/docs/09-install.md) and [backend/docs/10-attention.md](backend/docs/10-attention.md). These are dependency and selection foundations—not proof of inference acceleration.

## Backend development and traceable commits

The backend is developed in small modules, each with Python implementation, independent Markdown guide, and unittest tests. Start at **[backend/README.md](backend/README.md)** for the code ↔ docs ↔ test index and Windows startup commands.

Completed in the initial backend phase: local FastAPI bootstrap, Graph validation, bounded image assets, SQLite jobs, Rust queue choice, and an **opt-in Anima Base 1.0 generation adapter**. By default the inference backend remains disabled and job submissions return 503 unless the compatible model is installed and the adapter enabled. Qwen editing and GPU training are not implemented.

## Roadmap

- [x] 无 GPU 依赖的 Graph 执行计划、模型驻留策略、预算预检与单元测试基础
- [x] 固化仓库结构、目录归属、技术栈决策、源码-文档索引
- [ ] 实现统一模型适配器协议与测试
- [ ] 实现模型管理与精度检查
- [ ] 实现本地 Latent 缓存与模型卸载
- [ ] 实现 Text Encoder 缓存、CPU 编码与预取
- [ ] 实现 Diffusion Transformer LoRA 训练闭环
- [ ] 实现训练监控及 Epoch 采样对比
- [x] Anima Base 1.0 文字生成连接本地 FastAPI / SQLite / PNG 输出（尚待真实 GPU 实测）
- [ ] 接入其它模型生成与图像编辑工作流
- [ ] 在 8 GB / 16 GB / 24 GB 设备上分别测试显存、性能与效果

## Notes

LumaCarve 当前仍处于设计阶段。上述功能与性能目标不构成已完成实现或硬件兼容承诺。用户需遵守各基础模型、数据集及第三方依赖的许可要求。
