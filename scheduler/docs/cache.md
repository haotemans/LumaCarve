# cache.rs · 节点内容签名

`fingerprints(&[FingerprintNode])` 为节点及其上游依赖生成 SHA-256 签名。输入包含操作类型、参数、模型 revision、图像/资产哈希、上游签名和可选的随机 nonce。

- **不包含 UI 坐标与参数的暴露状态**：在画布拖动或切换参数视图不应导致缓存失效。
- 图片输入顺序、多个 LoRA 的顺序/权重、模型精确 revision 都应纳入签名；相同语义参数才复用。
- 对不可重放的随机操作必须明确 `volatile=true` 并提供 `volatile_nonce`，避免错误复用。
- 修改 Seed 只让与之相关的节点及下游失效，不重算无依赖的文本编码；实际是否缓存/如何释放由 Python 运行时负责。

该模块只计算**缓存键**，不保存大 Tensor，也不定义精确的 GPU 缓存淘汰策略。测试：`scheduler/tests/core.rs`。
