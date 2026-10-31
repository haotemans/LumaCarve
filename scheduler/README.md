# LumaCarve Rust Scheduler (CPU-only policy core)

> **当前实现：** Rust 调度的纯策略核心，不是 CUDA 或模型执行器。保留现有 Python API 和队列；尚未使用 Rust 驱动实际 GPU。

| 文件 | 文档 | 职责 | 测试 |
|---|---|---|---|
| `src/graph.rs` | [docs/graph.md](docs/graph.md) | DAG 拓扑顺序与输出生命周期 | `tests/core.rs` |
| `src/cache.rs` | [docs/cache.md](docs/cache.md) | 输入签名与缓存失效 | `tests/core.rs` |
| `src/queue.rs` | [docs/queue.md](docs/queue.md) | 一张 GPU 上的就绪任务优先级和取消状态机 | `tests/core.rs` |
| `src/resources.rs` | [docs/resources.md](docs/resources.md) | GPU/RAM 预算租约 | `tests/core.rs` |
| `src/lib.rs` + `Cargo.toml` | [docs/README.md](docs/README.md) | 模块导出与编译特性 | `tests/core.rs` |

从项目根目录运行：

```bash
cargo test --manifest-path scheduler/Cargo.toml --all-targets
```

**不要在 Rust 中执行扩散模型或管理 CUDA Tensor**。Python/PyTorch 仍负责真实权重加载、内存同步和 LoRA 训练。即使 Rust 编译成功，实际生图 API 仍需适配器；`POST /api/v1/jobs` 未配置推理引擎时返回 503。集成方案见 [ADR-0002](../docs/architecture/ADR-0002-rust-scheduler-comfyui-reference.md)。
