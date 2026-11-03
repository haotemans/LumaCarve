# Vue 前端 API 边界

代码：`../api.ts`、`../stores/studio.ts`。

Vue 入口只通过本地 FastAPI REST API 通讯。复用现有 `features/image-studio/api.ts` 及 `runtime.ts`，前端不加载 Python、Torch、Triton 或 Rust FFI。

接口对照：
- `GET /api/v1/runtime`：只读后端已知配置；GPU 未测量时必须显示 `—`。
- `POST /api/v1/jobs`：唯一工作流 JSON；`GET /api/v1/jobs`：历史列表；`GET /api/v1/jobs/{id}`：运行中任务；`POST /api/v1/jobs/{id}/cancel`：请求取消。
- `GET /api/v1/outputs/{id}`：只显示真实 PNG，必须验证 ID 格式。
- `GET /api/v1/models`：本地权重扫描；`GET /api/v1/downloads/catalog`：可信下载目录；`POST /api/v1/downloads`：显式开始模型下载；`GET /api/v1/downloads/{id}`：仅当前下载任务状态。

**安全约束**：维持现有服务端对 Origin/Host、模型路径与工作流格式的验证，前端不允许任意 URL / 任意路径推送至后端模型加载。下载需要后端主动开启并遵守模型许可证。UI 未实现的训练和编辑功能不构造假的接口响应。

`VITE_LUMACARVE_API_URL` 默认为 `http://127.0.0.1:8000`，用户可以在构建环境覆写。
