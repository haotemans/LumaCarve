# Vue 前端 API 边界

代码：`../api.ts`、`../stores/studio.ts`。

Vue 入口只通过本地 FastAPI REST API 通讯。复用现有 `features/image-studio/api.ts` 及 `runtime.ts`，前端不加载 Python、Torch、Triton 或 Rust FFI。

接口对照：
- `GET /api/v1/runtime`：只读后端已知配置；GPU 未测量时必须显示 `—`。
- `POST /api/v1/jobs`：唯一工作流 JSON；`GET /api/v1/jobs`：历史列表；`GET /api/v1/jobs/{id}`：运行中任务；`POST /api/v1/jobs/{id}/cancel`：请求取消。
- `GET /api/v1/outputs/{id}`：只显示真实 PNG，必须验证 ID 格式。
- `GET /api/v1/models`：本地权重扫描 + Anima 完整快照的真实就绪状态；`GET /api/v1/downloads/catalog`：可信下载目录；`POST /api/v1/downloads`：显式开始模型下载；`GET /api/v1/downloads/{id}`：仅当前下载任务状态。

**安全约束**：维持现有服务端对 Origin/Host、模型路径与工作流格式的验证，前端不允许任意 URL / 任意路径推送至后端模型加载。下载需要后端主动开启并遵守模型许可证。UI 未实现的训练和编辑功能不构造假的接口响应。

`VITE_LUMACARVE_API_URL` 默认为 `http://127.0.0.1:8000`，用户可以在构建环境覆写。

## 新增 API 与兼容性

- `GET /api/v1/jobs?limit=&offset=&state=`：`jobs` 列表向后兼容；新增 `total/counts/limit/offset`。任务筛选不再一次读取所有历史并在 JS 中过滤。
- `GET/POST /api/v1/datasets`：列举/创建真实训练集。
- `GET/POST /api/v1/datasets/{id}/images`：分页读取/受限 multipart 图像上传。
- `GET /api/v1/datasets/{id}/images/{sha256}`：图片；`PUT .../caption`：保存 UTF-8 标签并写入同名 `.tags.txt`；`DELETE .../{sha256}`：删除。

Vue 上传时每张图最多 25 MiB，单次选取 80 张，并发上传最多 3 路，不触及 GPU。失败会报告哪张图失败；重复文件保留后台 409 状态，防止静默覆盖。
