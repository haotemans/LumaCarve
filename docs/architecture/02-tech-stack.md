# 02 · 技术栈与选型原则

> 以仓库配置为准：**当前采用**不等于**所有功能已经完成**。版本使用兼容范围；具体 CUDA/PyTorch/模型适配组合必须在目标 GPU 验证后锁定。

| 层级 | 当前已使用 | 规划或约束 |
|---|---|---|
| Web UI | React 18、TypeScript、Vite 6、Lucide | 保持 SPA；按需加载大型界面，不额外引入无必要的 UI 框架 |
| 工作流编辑 | `@xyflow/react` 12 | Graph 为唯一工作流源，参数界面映射暴露字段；图结构序列化 `lumacarve.studio.workflow.v1` |
| Backend API | Python 3.11+、FastAPI、Pydantic 2、Uvicorn | REST `/api/v1`；进度后续优先 SSE，双向控制用 REST；不在 API 启动时加载模型 |
| 任务调度 | 线程调度与 SQLite 状态（已实现基础） | 计划隔离 CPU API 与单个 GPU 工作进程；Windows 使用 spawn；失败可恢复但不伪造任务完成 |
| 模型推理 | PyTorch、Diffusers、Transformers、Accelerate、Safetensors（已声明依赖） | **真实 Qwen/Anima/MOSS/Krea 适配器尚未实现**；每家族单独验证组件和编辑能力 |
| LoRA 训练 | PEFT、Datasets 等（已声明依赖） | 训练精度默认优先 BF16；训练循环/优化器/检查点待接入 |
| Attention | PyTorch SDPA、可选 FlashAttention / SageAttention（策略实现） | SDPA 回退；推理 vs 训练分开，不能仅凭包存在就认定兼容或提速 |
| 模型与依赖下载 | ModelScope + Hugging Face；清华/CERNET 镜像（已实现部分） | 固定版本、来源隔离、校验完整性、断点续传；国内/国际明确选择 |
| 持久化 | `sqlite3` + 文件系统 | 避免为了单机产品引入 Redis、PostgreSQL、Celery；输出元数据和文件存储分开 |
| Python 环境 | 仓库根目录单一 `.venv` + `tools/setup.py` | 模型共享 Python 环境，按需安装推理/训练依赖；GPU 扩展有兼容矩阵 |
| CI | GitHub Actions、TypeScript build、Python unittest | 增加目录结构检查；将来加适配器协议测试、CPU 烟雾测试、GPU 性能基准 |

## 性能基线

1. **不复制基础模型**：多个 LoRA Adapter 共享一个 Base Model 实例。
2. **驻留先于卸载**：如果能在 GPU 常驻且足够快，就不要每个采样步骤往返搬运 CPU/GPU。
3. **计算缓存有边界**：文本编码缓存、VAE latent 缓存以模型版本、精度、预处理和输入内容生成键。
4. **图形编辑与计算分离**：React Flow 只在 Graph 模式加载，参数模式不加载图形运行时，也不重复图状态。
5. **不迷信注意力库**：FlashAttention / SageAttention 与 SDPA 比较真实峰值显存、延迟、图像质量和模型兼容。
6. **8/16/24 GB GPU 为目标档位，不是硬件保证**：每个模型基于实测设置精度、分块、卸载阈值。

## 现在不引入的重型组件

- 不为本地单用户应用添加微服务、Kubernetes、Redis、Kafka 或 Celery。
- 不为每个模型创建独立 Python 虚拟环境。
- 不并行引入两个工作流引擎或两套参数状态。
- 桌面打包可以将来评估 Tauri / Python sidecar，但**目前不提前引入 Electron/Tauri 依赖**，先确保本地 WebUI 和推理闭环可用。
- 不在未实测前把 FP8、INT8 和大规模异步预取宣布为默认优化。

## 升级与依赖锁定

当前 `frontend/package.json` 和 `backend/pyproject.toml` 是带范围的依赖声明，**并非完全锁定的可复现构建**。下一阶段按 Windows CUDA 与 Linux CUDA 平台生成分层锁文件；不要统一用一个 CUDA wheel 索引覆盖全部依赖，也不在普通安装时随意升级 PyTorch。先验证 GPU 驱动、计算能力及 Qwen/Anima 等模型要求。

## 文档与测试

新增源码同时新增同名或领域级 Markdown。每次小 commit 包含同一个模块的代码、文档、测试和必要的迁移说明，禁止一次提交混合大量不相关 UI 和 CUDA 变更。
