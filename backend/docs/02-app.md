# 02 · HTTP 服务与健康检查（app.py）

对应代码：\`lumacarve_server/app.py\`。对应测试：\`tests/test_server.py\`。

技术栈：FastAPI / Uvicorn；Python 3.11+。通过 \`create_app(settings)\` 注入配置，方便无 GPU 单元测试。重型模型依赖不在 HTTP 进程导入时加载。

运行：
\`\`\`powershell
cd backend
py -m pip install -e ".[dev]"
py -m uvicorn lumacarve_server.app:app --host 127.0.0.1 --port 8000
\`\`\`
打开 \`http://127.0.0.1:8000/docs\` 访问自动生成的 OpenAPI 文档。

接口：
- \`GET /api/v1/health\`：API 存活，不等同于模型可用。
- \`GET /api/v1/runtime\`：目前报告 \`not_connected\`，不会虚构 GPU 显存。

请求由 Host 白名单和 Origin 白名单限制。CORS + Origin 检查仅是本地演示的基本安全控制，并非互联网部署的身份鉴权。

**状态：** API 基础启动已实现；模型列表、上传、工作流和生成任务在后续按模块增量接入。


`GET /api/v1/runtime` 另提供 `queue_scheduler`（实际 Rust/Python 调度后端）和 `queue_scheduler_error`（后台队列故障；正常为 null）。这个状态读取 **当前 FastAPI 实例** 的队列，而不是模块级全局应用，以保证测试和多个隔离实例的数据正确。


## Anima 可选模型执行

`LUMACARVE_INFERENCE_BACKEND=anima` 时，API 在 lifespan 创建轻量 `AnimaAdapter`，仅检查完整本地 ModularPipeline 目录与依赖是否已安装；首次提交并领取生成任务后才导入 Torch、初始化 CUDA 和加载模型。`GET /api/v1/runtime` 同时报告 `configured_engine` 与可用的 `engine`，GPU 信息依然标记未测量。详细信息见 [17-anima-adapter.md](17-anima-adapter.md)。

## Runtime Snapshot：真实状态，不伪造 GPU 遥测

`GET /api/v1/runtime` 仅收集现有 Python Settings、单队列状态和本地模型路径/依赖存在性，不会导入 Torch、调用 CUDA 或启动基准测试。

- `configured_engine`：用户指定的推理后端，`engine`：本地文件与依赖检查后的后端选择；**都不等于 GPU 已加载或已经成功出图**。
- `gpu.measured=false`、`gpu.available=null`：GPU 没有被此端点探测；`null` 表示未知，不是“没有 GPU”。
- `inference_offload`：当前基础模型卸载选择（`auto | full | model_cpu`）。`memory_planner.adaptive="not_implemented"` 表示之前讨论的 AMEP 智能预测式资源规划器还没有实际接入；不能把现有 Diffusers 自动 CPU 卸载叫做 AMEP。
- `optimization.state="configured_only"` 与 `optimization.validated_on_gpu=false`：`optimization.anima.adaln/rope/residual/ffn` 的 `off|experimental` 仅表示 **环境配置**，并非 Triton Kernel 已经被实际安装、编译、使用或证明更快。
- 因为普通页面只需在进入工作室时读取一次，不需要实时频繁查询 GPU 显存。

前端由 `frontend/src/features/image-studio/runtime.ts` 严格验证这一结构，并通过 `RuntimeStatusPanel.tsx` 只读展示。实际状态刷新由用户主动触发；不为展示面板采集额外 GPU 性能数据。


## 数据集与队列状态更新

`create_app()` 除创建原有单实例 JobQueue 外，还会创建轻量 `DatasetStore`，索引统一保存在 `LumaCarveData/datasets.sqlite3`。数据集路由与所有已有 API 共用相同的本地 Origin 和 TrustedHost 安全规则。

运行时状态新增 `queue.counts`、`queue.capacity`、`queue.running_worker`，全部由现有任务账本读取，不执行 Torch/CUDA 检查。`gpu.measured=false` / `gpu.available=null` 的真实性约束保持不变；不得把队列容量当成 GPU 显存容量。
