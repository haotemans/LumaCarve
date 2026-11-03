# api.ts · Anima 本地图像任务 API

对应源码：`../api.ts`。前端只和本地 FastAPI 的 `/api/v1/jobs`、`/api/v1/outputs` 通讯，不包含生成模型或任何 CUDA 调用。

- `submitImageJob(workflow)` 提交**唯一 Graph JSON** 到后端，设置交互式任务优先级。
- `getImageJob(jobId)` 查询 SQLite 中的真实任务状态和错误。
- `cancelImageJob(jobId)` 请求协作取消；如果 GPU 正在采样，服务端可能只在整张图完成后处理。
- `outputFromJob(job)` 验证后端输出 ID 后生成 PNG URL。没有真实结果时绝不显示示例图片为已生成作品。

本地后端地址默认 `http://127.0.0.1:8000`，开发时可用 `VITE_LUMACARVE_API_URL` 覆盖；不自动扫描网络服务，也不依赖代理/外网。

验证入口：`cd frontend && npm run build`。后端 Python 单元测试覆盖提交、执行、输出文件和失败路径。前端浏览器端端到端测试仍未实现。

## 与运行状态模块共享的本地 API 地址

`api.ts` 导出同一个 `API_ORIGIN` 常量供 [runtime.ts](runtime-status.md) 使用。RuntimeStatusPanel 只读 `GET /api/v1/runtime`，并不使用生成任务轮询接口；没有后台 GPU 监控。后端区分已配置选项、模型文件就绪和 GPU 尚未测量。
