# queue.rs · 就绪任务 / 取消状态机

`JobScheduler`：入队唯一任务 ID、最大活跃队列预算、交互/普通/后台三级优先级、单 GPU 同时只允许运行一个任务。

公平性：最多连续执行 3 个交互任务；如果其他优先级任务正在等待，下一次优先考虑非交互任务。相同优先级严格先入先出。

取消行为：等待中任务直接标记 cancelled；运行任务只记录 `cancel_requested`，由 PyTorch 执行循环在 CUDA 安全同步点协作停止；**Rust 不强制打断内核，也不释放正在执行的模型**。结束时取消请求优先于成功状态。

**单机 SQLite 是唯一持久化状态账本**；过渡期 Python `JobStore` 和 Rust `JobScheduler` 不得形成两个独立执行队列。首阶段该模块尚未接管 Python JobQueue。测试：`scheduler/tests/core.rs`。
