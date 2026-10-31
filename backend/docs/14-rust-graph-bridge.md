# 14 · Python Graph 与 Rust Scheduler 桥接

对应代码：`lumacarve_runtime/rust_bridge.py`；测试：`tests/test_rust_bridge.py`。

`compile_preferred` 将原有 `WorkflowNode` 转为简短 JSON 后调用可选 Rust `compile_graph_json`，将结果还原为现有 `ExecutionPlan`。这样现有 `lumacarve_server/workflows.py` 与 Python 图像任务接口**不需要修改对外 JSON schema**。

- 未安装 `lumacarve_scheduler`：保持旧 `compile_workflow` 行为，并报告 `python-fallback`。
- 已安装：优先使用 Rust 编译，校验返回节点集合、输出集合及生命周期字典。Rust 抛错或返回畸形计划则显式失败，不暗中退回 Python。
- Python 依然做模型语义、节点字段、LoRA 权重和输入图像的校验；Rust DAG 编译只负责执行顺序。
- 运行时可通过 `scheduler_backend()` 了解当前是否加载了 Rust，但该值**不代表推理引擎可用**。

`scheduler/tests/core.rs` 检验 Rust 算法；`backend/tests/test_rust_bridge.py` 校验 Python 回退和真实 Rust 扩展的等价性。GitHub CI 会使用 maturin 在临时 `.venv` 中构建并安装 Rust 扩展后运行对照测试。

**性能与内存边界：** 每次编译都通过小 JSON 传递 DAG 元数据，绝不会传图片或张量。后续模型执行和 JobQueue 真正切换 Rust 调度前还需要生命周期、重启与取消契约测试。
