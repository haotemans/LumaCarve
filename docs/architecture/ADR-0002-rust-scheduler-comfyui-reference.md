# ADR-0002 · 参考 ComfyUI 的图执行设计；Rust 负责调度，Python 负责模型计算

- 状态：Accepted for incremental implementation（已决定方向，按模块渐进接入）
- 日期：2026-11-01
- 影响范围：Graph 运行时、任务队列、缓存、显存仲裁、Python/Rust 接口
- 前置决策：[ADR-0001](ADR-0001-modular-monorepo.md)

## 参考来源（研究原理，不复制源码）

ComfyUI 官方源码（阅读于 2026-11-01）：
- [comfy_execution/graph.py](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_execution/graph.py)：`DynamicPrompt`、`ExecutionList`、依赖阻塞、执行顺序、惰性输入。
- [comfy_execution/caching.py](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_execution/caching.py)：节点输入签名、祖先依赖、缓存策略。
- [execution.py](https://github.com/Comfy-Org/ComfyUI/blob/master/execution.py)：执行、缓存协调与异步节点。
- [comfy/model_management.py](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/model_management.py)、[model_patcher.py](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/model_patcher.py)：显存状态、模型/LoRA 补丁管理。

**只借鉴架构机制和公共接口思想；不要照搬 ComfyUI 的 GPL 代码，也不宣称与 ComfyUI 自定义节点二进制兼容。** 将来若做第三方工作流转换器，需要独立维护格式与许可边界。

## 核心决策：三层执行职责

```text
React + React Flow（Graph 编辑 / 参数视图）
                   │ 单份 JSON 工作流，经过 Python API 校验
                   ▼
FastAPI / SQLite（认证边界、模型/素材目录、任务持久化）
                   │ 小型结构化消息；无 Tensor 穿越边界
                   ▼
Rust Scheduler（图计划、节点就绪队列、取消、缓存键、资源预留）
                   │ 按节点调度 Python Adapter，执行结束回写状态
                   ▼
Python / PyTorch（TE / VAE / DiT / LoRA、CUDA kernel、模型加载卸载）
```

Rust **不**负责实现 CUDA 扩散算子、直接持有 Tensor 数据，也不把各类模型改写成 Rust。当前单 GPU / 本地工作台优先使用 **PyO3 同进程绑定**，避免引入新的独立调度服务、TCP/IPC 和第二套 Python 环境。成熟后若需要崩溃隔离，再考虑 GPU worker 子进程和有界控制消息（绝不通过 JSON/IPC 移动大量张量）。

## Rust Scheduler 的长期职责

1. **Graph 编译**：拓扑依赖、稳定执行顺序、准备/执行阶段、输出活跃区间、类型化端口（下一版工作流）、惰性输入。
2. **增量计算**：节点签名由节点类型、参数、**模型版本/哈希**、LoRA 顺序与强度、上游签名和外部资产哈希构成。编辑 UI 坐标/暴露顺序不应触发重复推理；修改 Seed 应使依赖的采样与下游失效，而不让无关编码自动失效。
3. **任务调度**：训练/生成共享一份可恢复的调度账本；优先级、公平性、队列背压、协作取消、安全暂停。首版单 GPU 同时只运行一个重型任务，不在扩散 step 内强行抢占。
4. **内存预算和租约**：Rust 决定何时值得保留模型、何时尝试卸载；Python 模型适配器提供真实 CUDA 显存测量、权重搬迁/同步及实际生命周期。不得仅凭 Rust 的估算声称显存释放成功。
5. **数据边界**：Rust 持有小的图/任务元数据，不持有图像、Latent、Diffusion Transformer 权重或 CUDA Tensor；缓存大对象的所有权仍在 PyTorch worker 内。

## 现实限制

- **Rust 不会让扩散模型内核自动变快**。影响出图耗时最大的仍是 GPU 计算、Attention、内存带宽和模型搬运。Rust 的价值是确定性调度、轻量控制状态和安全资源仲裁。
- Python 3.11 有全局解释器锁；PyO3 调用 Python 模型代码时仍受 Python 运行时约束。Rust 调度不应持锁等待 GPU kernel。
- Graph 的当前格式为 `lumacarve.studio.workflow.v1`：节点连线尚未包含显式 typed socket。Rust v0 先保留 v1，**不悄悄切成 ComfyUI prompt 格式**。可另做 v2 迁移器。
- 当前 `backend/lumacarve_server/jobs.py` 和 `lumacarve_runtime/graph.py` 仍在使用 Python 实现；过渡期保留回退，但不能让两套执行队列同时驱动 GPU。
- Rust 扩展是可选编译依赖，编译失败时继续用现有 Python API（未接入 GPU 时仍返回 503）。打包安装时同一个项目 `.venv` 接收扩展 wheel。

## 分阶段落地顺序

1. 独立 `scheduler/` Rust crate：输入 v1 JSON，输出拓扑计划和中间结果最后使用位置；带 Cargo 单元测试。
2. Rust 队列状态机/缓存签名：分离纯策略与 PyTorch 执行；测试任务取消、无环、独立分支失效。
3. PyO3 在同一 Python 进程加载；用对照测试验证 Python/Rust 图执行顺序与最后引用位置一致。
4. 逐步让 Python `JobQueue` 使用 Rust 调度决策，SQLite 继续是**唯一持久化任务真相**；迁移完成才删旧算法。
5. 接入真实模型 Adapter 后测量 GPU 活跃度、内存峰值、缓存命中率及 Python ↔ Rust 边界开销。

回退条件：Rust 扩展不可用/版本不匹配时不得破坏 API；无 GPU CI 仅证明调度正确性，不是模型推理完成。
