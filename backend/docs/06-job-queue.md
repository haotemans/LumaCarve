# 06 · 任务持久化与单 GPU 队列（jobs.py）

对应代码：`lumacarve_server/jobs.py`、`routers/jobs.py`；测试：`tests/test_jobs.py`。

SQLite 任务账本记录状态 `queued/running/completed/failed/cancelled`、工作流 JSON、输入资产 ID、执行结果/错误与创建更新时间。

HTTP API：
- `POST /api/v1/jobs`：校验 Graph 与必需图片/蒙版，然后进入队列；**未接入推理适配器时返回 503，绝不悄悄入队或伪造结果**。
- `GET /api/v1/jobs`、`GET /api/v1/jobs/{id}`：读取任务历史。
- `POST /api/v1/jobs/{id}/cancel`：队列中任务直接取消，运行中请求协作取消。

调度：单 worker 串行执行 GPU 图像任务；后续训练也必须与之共用 GPU 资源仲裁而不能单独抢显存。重启会把未完成的 `running` 标为 `failed/server_restarted`。`queued` 项留在持久化存储中；后台 worker 会检查 `adapter.ready`，只有接入真正可用的模型适配器才会继续处理；未连接时保留排队记录，不会误标记为失败。任务日志不保存任何假图片。

取消：推理适配器需要定期检查 `threading.Event` 并在模型安全同步点停止，否则只是申请取消。该版本没有强行中断 CUDA 内核。

**目前状态：** 队列、数据库及 API 验证已完成；`DisabledInference` 为显式不可用适配器，没有安装/运行真正模型。


## Rust 调度与 SQLite 的统一领取

任务可选择 `priority=interactive|normal|background`，创建图像任务的 HTTP API 默认 interactive。旧数据库自动补上 `priority` 列（默认 normal）。连续交互任务计数持久化在 `scheduler_state`，重启后仍保留公平性策略。

`JobStore.claim_next()` 使用 SQLite `BEGIN IMMEDIATE` 获取一致的 queued 快照，再调用 `queue_bridge.choose_pending_job()`。后者优先通过 PyO3 使用 Rust 的纯选择函数，扩展不存在时走同语义 Python 回退；只有数据库事务成功将选中任务更新到 running 才能执行 Adapter。SQLite 是唯一任务状态来源，没有第二套 Rust 执行队列。

`JobQueue` 的本进程锁保证领取与取消标记不会竞态丢失；GPU 推理在锁外运行。该版本仍需要跨进程所有权锁来严格禁止两个 FastAPI 实例同时控制同一显卡。


## 跨进程唯一所有权

原子领取只防止数据库重复运行，**不能阻止两个服务进程分别持有 GPU 权重**。现在 `JobQueue.start()` 会先获取 [独占进程锁](16-single-instance-lock.md)，成功后才恢复/标记异常退出的 running 任务。仅实例化 `JobStore` 不会干扰已经在运行的任务。锁文件不删除，worker 确认结束后才释放。


调度异常（例如 Rust wheel 与 Python 不兼容）会让 worker 停止领取新任务、保留 SQLite 中的 queued 记录，并在 `GET /api/v1/runtime` 返回 `queue_scheduler_error`；后续提交明确返回 503，供用户修复扩展后重启。


## Windows SQLite 文件句柄修复

此前使用 `with sqlite3.connect(...) as db` 只处理事务提交/回滚，**不会关闭连接**；Windows 临时目录清理因此触发 `WinError 32`。现在 `JobStore._connect()` 是专用 Context Manager，所有查询/原子领取均在事务结束时 `connection.close()`，同时保留异常回滚和连接独占锁。`test_jobs.py` 验证离开上下文后连接不可使用，Windows CI 再检验真实文件释放。


## 2026-11 · 高效分页与只读队列快照

`GET /api/v1/jobs?limit=30&offset=0&state=queued` 返回 `jobs`、`total`、`counts`（queued/running/completed/failed/cancelled）、`limit`、`offset`。默认 `limit=50`，最大 100；非法状态、负数页偏移均返回 422。该接口仍兼容原先仅读取 `jobs` 的客户端。

`JobStore.list()` 已从 **先取 N 个 ID 再逐个开启 SQLite 连接读取** 改为一次有界 SQL SELECT，避免刷新大历史列表时 N+1 连接开销。`JobStore.counts()` 仅按状态分组计算，不执行 GPU 查询。`GET /api/v1/runtime` 的 `queue` 返回现有状态数量和最大队列容量，前端无需另启 GPU 轮询服务。
