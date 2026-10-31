# 16 · GPU 队列单实例所有权（instance_lock.py）

对应代码：`lumacarve_server/instance_lock.py`，`jobs.JobQueue` 在启动/结束时获取、释放锁；测试：`tests/test_instance_lock.py` 和 `test_jobs.py`。

## 为什么需要

SQLite 的 `BEGIN IMMEDIATE` 能确保**领取任务是原子的**，但不足以禁止多个 API 进程分别持有独立的 CUDA 模型。因此引入跨进程文件锁：

- Linux 使用 `fcntl.flock(..., LOCK_EX|LOCK_NB)`，Windows 使用 `msvcrt.locking(..., LK_NBLCK)`。
- 锁文件存放在任务数据库旁边，**始终保留**，只释放 OS 锁；删除正在使用的锁文件可能导致不同进程各自锁住不同 inode。
- 第二个 API 进程如果试图启动 GPU JobQueue，会明确失败，不会悄悄运行第二个 worker。
- 只有拿到独占所有权后才可以把旧的 `running` 标记 `failed/server_restarted`。单纯打开 `JobStore` 不再重置别的进程正在执行的任务。
- Worker 完成退出后才释放所有权。如果线程仍在执行，关闭过程拒绝提前解锁，避免新的服务错误地并发加载模型。

**局限**：这是一台本地机器、共享同一数据目录的单 GPU 队列锁。未来多 GPU 任务要按设备 ID 单独锁定或使用全局资源仲裁；本地锁不是面向网络分布式任务的租约协议。HTTP 默认仍只监听 127.0.0.1。
