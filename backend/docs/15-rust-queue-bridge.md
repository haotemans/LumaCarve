# 15 · Rust 调度决策 / SQLite 快照桥接（queue_bridge.py）

源码：`lumacarve_runtime/queue_bridge.py`；测试：`tests/test_queue_bridge.py`，Rust 对照测试在 `scheduler/tests/core.rs`。

## 职责

`choose_pending_job(pending, streak)` **仅选择任务**，不更新 SQLite，不启动 GPU，也不拥有其他内存队列。pending 必须来自一个 SQLite 写事务内的一致快照，成员含 `id`、`priority`（interactive / normal / background）、持久化 `sequence`（SQLite rowid）。

Rust PyO3 已安装：调用 `choose_queued_job`，并与 Python 参考决策检查一致；扩展未安装：执行 Python 同语义回退。如果扩展安装后损坏或返回非法候选，直接报错，不跳过该错误执行另一任务。

策略：交互优先，同优先级 FIFO；连续 3 个交互任务后，从等待中的非交互任务里选择**最早进入数据库**的任务。选择后由 SQLite 的条件 UPDATE 原子领取，绝不创建第二套队列。由于 SQLite 是唯一真相，服务重启后可重新选择排队项。运行中 CUDA 取消仅由 Adapter 在安全点执行。

## 实际状态

本模块当前实现并测试了选择策略。连接到真实数据库的原子领取入口在 `jobs.py` 实现；推理适配器未连接时任务 API 仍返回 503。
