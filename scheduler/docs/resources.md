# resources.rs · 预算租约

`MemoryArbiter` 以 `ResourceBudget`（GPU/RAM 字节）和唯一任务租约 ID 管理保留量。超预算时拒绝、释放租约时精确扣回、使用 `checked_add` 防止整数溢出。

这**不是 PyTorch CUDA Allocator**：只管资源预留计划，不分配、搬迁、加载或卸载任何张量；Python ModelBackend 必须负责 GPU 同步、真实显存用量监测、卸载以及失败回滚。

测试：`scheduler/tests/core.rs` 超预算、重复租约、释放后重新分配；下一阶段加入实际显存反馈、预测误差与预算动态调整。
