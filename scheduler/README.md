# LumaCarve Rust Scheduler (CPU-only policy core)

> **当前实现：** Rust 调度的纯策略核心，不是 CUDA 或模型执行器。保留现有 Python API 和 SQLite 唯一队列；已由 Rust 优先选择待办任务，尚未使用 Rust 驱动实际 GPU 模型。

| 文件 | 文档 | 职责 | 测试 |
|---|---|---|---|
| `src/graph.rs` | [docs/graph.md](docs/graph.md) | DAG 拓扑顺序与输出生命周期 | `tests/core.rs` |
| `src/cache.rs` | [docs/cache.md](docs/cache.md) | 输入签名与缓存失效 | `tests/core.rs` |
| `src/incremental.rs` | [docs/incremental.md](docs/incremental.md) | 输出驱动的增量执行/缓存复用规划 | `tests/incremental.rs` |
| `src/queue.rs` | [docs/queue.md](docs/queue.md) | 一张 GPU 上的就绪任务优先级和取消状态机 | `tests/core.rs` |
| `src/resources.rs` | [docs/resources.md](docs/resources.md) | GPU/RAM 预算租约 | `tests/core.rs` |
| `src/python.rs` + `pyproject.toml` | [docs/python-bridge.md](docs/python-bridge.md) | PyO3 Graph、队列、资源租约绑定（可选） | `backend/tests/test_rust_bridge.py` + wheel smoke test |
| `src/lib.rs` + `Cargo.toml` | [docs/README.md](docs/README.md) | 模块导出与编译特性 | `tests/core.rs` |

从项目根目录运行：

```bash
cargo test --manifest-path scheduler/Cargo.toml --all-targets
```

PyO3 wheel 可通过 maturin 编译并安装进项目**同一个 `.venv`**；已安装时 Python Graph 校验优先使用 Rust，缺失时使用 Python 计划编译。Rust 队列及资源仲裁尚未接管执行器；详见 [桥接文档](docs/python-bridge.md)。

**不要在 Rust 中执行扩散模型或管理 CUDA Tensor**。Python/PyTorch 仍负责真实权重加载、内存同步和 LoRA 训练。即使 Rust 编译成功，实际生图 API 仍需适配器；`POST /api/v1/jobs` 未配置推理引擎时返回 503。集成方案见 [ADR-0002](../docs/architecture/ADR-0002-rust-scheduler-comfyui-reference.md)。

注意：`scheduler/target/` 与 wheel 是本地编译产物，已由根目录 `.gitignore` 忽略，不能提交到仓库。

## 与 Python 服务衔接

Python JobStore 使用 `BEGIN IMMEDIATE` 原子领取 Rust 策略推荐的任务，持久化状态和公平计数均在 SQLite；不存在第二套 GPU 执行队列。`instance_lock.py` 使用 Windows/Linux 系统文件锁隔离不同服务实例。`plan_incremental_json` 已实现但尚未被真实模型 Adapter 消费。
