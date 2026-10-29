# 08 · 依赖分层与统一环境（pyproject.toml）

对应代码：`backend/pyproject.toml`、`lumacarve_server/installer.py`（下一模块）；测试：`tests/test_installer.py`。

## 原则

**全项目统一一个 Python 虚拟环境：仓库根目录的 `.venv/`。** WebUI 通过 HTTP 调用同一 Python 服务；不为每个模型、Graph 模式或训练任务创建额外环境。

依赖分为：

| 依赖组 | 功能 | 默认 |
|---|---|---|
| 核心 | FastAPI、Pydantic、Uvicorn、Pillow 等 | 是 |
| `inference` | PyTorch、Diffusers、Transformers、Accelerate、Safetensors | 图像工作模式 |
| `training` | PEFT、Datasets、TensorBoard 等训练预备组件 | 按选项加入同一环境 |
| `attention-build` | FlashAttention 源码编译辅助工具 Ninja、packaging、psutil | 仅需要时 |
| `flash` | 独立 `flash-attn` (FlashAttention-2) | CUDA/平台验证后尝试 |
| `sage` | `sageattention` (SageAttention) | CUDA/平台验证后尝试 |
| `dev` | HTTP API 单元测试的 httpx | 开发安装 |

**PyTorch 不能盲目通过默认 PyPI 安装**：NVIDIA GPU 应选择与驱动兼容的官方 CUDA wheel；CPU 环境选择 CPU wheel。项目设置脚本首先安装 PyTorch，然后安装 Python extras，避免把 CUDA 版本悄悄换掉。

## FlashAttention / SageAttention 注意事项

- **FlashAttention-2** 提供精确注意力的前向与反向；官方主要以 Linux + CUDA Toolkit 为安装路径。原生 Windows 源码构建仍存在兼容限制。文档：https://github.com/Dao-AILab/flash-attention
- **SageAttention** 主要优化推理注意力，采用低比特计算；不能在未验证反向传播能力时替代训练的 FlashAttention。官方源码：https://github.com/thu-ml/SageAttention
- **PyTorch SDPA** 是所有环境的安全回退方案：CUDA 情况下其自身可自动调用融合 FlashAttention 类内核，**不必同时安装独立的 flash-attn 包**。文档：https://docs.pytorch.org/docs/stable/generated/torch.nn.functional.scaled_dot_product_attention.html
- 同时安装两种库不代表同时运行两个注意力内核：每次注意力调用只选一个后端，优先实测性能与显存后决定。
- 仅当可获得兼容的官方依赖、CUDA Toolkit 和 GPU 时进行编译。Windows 推荐先使用 SDPA，之后选择经过验证的匹配 wheel，避免从不可信的第三方下载编译包。

未运行 `tools/setup.py` 前，**依赖只是声明，并没有下载到用户电脑**。具体命令和安装报告见 [09-install.md](09-install.md)。
