# python.rs · PyO3 绑定与同环境安装

对应 Rust `src/python.rs`、`pyproject.toml` 和 `backend/lumacarve_runtime/rust_bridge.py`。Python 单元测试 `backend/tests/test_rust_bridge.py`，CI 通过 maturin 构建临时 wheel 后验证真实扩展可导入。

## 模块 API

- `compile_graph_json(nodes_json)`：JSON 数组 `NodeSpec` → JSON `ExecutionPlan`。
- `fingerprints_json(nodes_json)`：小型节点元数据 → JSON SHA-256 签名。
- `choose_queued_job(pending_json, consecutive_interactive)`：读取 SQLite 持久队列快照，返回 `(任务 ID, 新连续交互次数)`，**不修改队列**。
- `RustJobScheduler(maximum_active)`：`submit(id,priority)`、`start_next()`、`cancel(id)`、`should_cancel(id)`、`finish(id,succeeded)`。
- `RustMemoryArbiter(gpu_budget,cpu_budget)`：`reserve(id,gpu_bytes,cpu_bytes)`、`release(id)`、`used()`。

`priority` 为 `interactive/normal/background`。取消运行中任务只产生取消请求，不能强制抢占 CUDA。

## 安装原则

只有一个项目根 `.venv`。后端 API 安装到此环境，Rust 扩展也安装到同一个环境，**不启动独立 Rust HTTP 服务，不为 Rust 再建 Python 环境**。

普通用户推荐运行一键安装器：`py -3.11 tools/setup.py --region cn --torch cu128 --scheduler auto`。如果未安装 Rust 编译器，明确回退 Python Graph，安装报告写入原因。要求 Rust 时使用 `--scheduler required`。

开发者手动安装示例（从项目根目录）：

```powershell
.\.venv\Scripts\python.exe -m pip install "maturin>=1.7,<2"
.\.venv\Scripts\python.exe -m maturin develop --manifest-path scheduler/Cargo.toml --features python
```

需要本机 Rust 编译器和 Cargo。适用于 Windows/Linux；目前未提供经过 GPU 适配验证的二进制发行 wheel。

## 兼容保证

- 如果扩展不存在，`rust_bridge.py` 使用已存在的 Python Graph 编译器，API 仍能启动。
- 如果扩展存在但返回异常/畸形计划，**报错而不隐藏回退**，避免两个执行器输出不一致。
- Python/Rust 用相同的 v1 `node_id/operation/depends_on/components` 结构，入 Rust 前保留 Python 的模型语义和节点类型验证。
- 禁止传输像素、Latent、Torch Tensor 或模型权重；JSON 只放图元信息和少量参数。

**当前集成阶段：**真实 Graph 编译可选择 Rust；Rust 的队列及资源仲裁 Python 类型已经暴露，但 `JobQueue`/CUDA 尚未切换到 Rust 调度，防止迁移期双重执行。


CI 在 Linux 与 Windows 上分别执行 Cargo 调度策略测试，并在两种系统上使用 maturin 构建对应的 PyO3 wheel、安装到虚拟环境、运行 Graph 回退/等价性测试。这是 Python 3.11 平台构建验证，不代表已对 CUDA 推理性能进行实测。
