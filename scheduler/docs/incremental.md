# incremental.rs · ComfyUI 启发的按需增量执行计划

对应代码：`src/incremental.rs`；测试：`tests/incremental.rs`。**重新设计的 Rust 算法，没有复制 ComfyUI GPL 源码。**

## 规则

对调用者指定的输出节点计算依赖闭包，仅规划到达输出所需的子图。若某个中间节点的 SHA-256 内容签名与已存储结果匹配、`available=true` 且节点不是 `volatile`，就标记 `reuse` 并停止继续遍历它的上游。这允许重复使用缓存文本编码结果、VAE Latent 等，不会因为 Graph UI 节点坐标改变而重复计算。

- `execute`：Python 执行该节点并按需要缓存结果；
- `reuse`：Python 必须真的拥有此节点对应的完整缓存输出；Rust 不会自己持有 GPU Tensor；
- 失效：Seed、LoRA 列表/权重、模型修订及输入图片哈希应进入上游节点签名；任何修改都必须传播到下游；
- 不可重放节点始终执行，且需要显式 nonce；不能把随机生成的实时结果当成永久缓存；
- 被淘汰或不存在的结果必须设置 `available=false` 或从 cache snapshot 删除，不能仅凭旧哈希声称缓存命中。

`plan_incremental(nodes, known, requested_outputs)` 只输出 `IncrementalPlan`（需要执行/复用的节点和签名）。它**不**保存图片、Tensor、LoRA 权重，不会修改 SQLite，也不负责 GPU 的实际缓存生命周期。

## 与现有后端的关系

当前完成 CPU-only Rust 计划与测试；下一小批通过 PyO3 暴露可选计划 API，之后由 Python 模型执行器在开始任务时传入**真实有效的缓存对象目录**，才可以省略 Text Encoder / VAE 等节点的实际计算。

只有缓存对象真正存在、模型与数据版本匹配且运行时保证引用有效，才算完成 ComfyUI 风格增量计算。不能把这个静态计划模块宣称为真实模型加速。


## 可选 Python 绑定

通过 maturin 构建 `lumacarve_scheduler` 扩展后，`plan_incremental_json(nodes,cached,outputs)` 返回 JSON 格式的执行/复用步骤；`fingerprints_json` 给出相同输入对应签名。Python 只有在缓存对象真实可访问时才应传入 `available=true`。真实 GPU 执行器尚未使用该计划，不可声称已经节省扩散计算。
