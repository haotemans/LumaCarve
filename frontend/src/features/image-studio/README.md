# Image Studio · 框架无关模块

此目录现在只保留可由 Vue 3 前端复用的 TypeScript：`workflow.ts`（唯一的 Graph JSON 数据模型和预设校验）、`api.ts`（本地真实作业/PNG）、`runtime.ts`（严格只读状态解析）。

公开图形化工作台已经迁移到 `frontend/src/vue/views/StudioView.vue`，其说明见 [Vue Studio](../../vue/docs/studio.md)。**没有 React、React Flow 或 GraphCanvas 的运行时代码。**

现有 `lumacarve.studio.workflow.v1` 与服务端 `backend/lumacarve_server/workflows.py` 相互兼容；迁移没有改变执行图协议。

文档：[工作流 JSON](docs/workflow.md) · [API](docs/api.md) · [Runtime](docs/runtime-status.md) · [术语](GLOSSARY.md)。

测试：`cd frontend && npm run test && npm run build`。
