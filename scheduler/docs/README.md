# Rust Scheduler · 模块边界

对应 `src/lib.rs`、`Cargo.toml`。Rust 标准库驱动图元信息调度，serde/serde_json 提供 JSON 序列化，sha2 提供稳定 SHA-256 节点签名，PyO3 为 **可选** Python 扩展特性。

`cargo test` 默认不会导入 Python、PyTorch、CUDA，减少测试环境负担。各算法由 `scheduler/tests/core.rs` 验证。API、SQLite 存储及 GPU 执行器仍由 Python 管理；以后通过 PyO3 将 Rust 调度决策映射成轻量对象，**不要把图像、Latent 或 Tensor 经 JSON 跨边界传输**。

许可证：这个模块只参考 ComfyUI 公共架构思想，算法从头编写。没有复制其 GPL 代码。对 ComfyUI 的具体参考点见 [ADR-0002](../../docs/architecture/ADR-0002-rust-scheduler-comfyui-reference.md)。

项目尚未附带独立许可文件，不能默认认为 ComfyUI GPL 源码或其他外部实现可以复制进本仓库。Rust 代码是单独实现的算法与接口；对外发布前应明确项目许可证及第三方依赖许可。
