# Vue 3 其它图形化工作台

**对应源码**：`../views/TrainingView.vue`、`GalleryView.vue`、`ModelsView.vue`、`DatasetsView.vue`、`TasksView.vue`、`SystemView.vue`。

- **作品画廊**：读取 SQLite 真实作业列表，对 `completed` 任务严格验证输出 ID 后显示 PNG 缩略图；无文件时只显示空状态，不使用虚构示例。
- **模型管理**：区分普通本地权重文件与后端已发现的完整 Anima ModularPipeline 快照；不能把任意浏览器选中的路径称为可运行模型。只读已索引的本地模型文件与下载目录；下载按钮触发真实 `POST /api/v1/downloads`，仅下载被后端允许的可信条目；只有用户启动下载后才轮询相应下载任务，不构造虚假的进度条。
- **任务队列**：只读真实 `GET /api/v1/jobs?state=...&limit=30&offset=...`；显示各状态数量、分页、手动刷新和取消队列/运行中的任务；不假设能强制终止正在执行的 CUDA Kernel。
- **运行环境**：只读配置、未知的 GPU VRAM、基础 offload 策略和实验内核配置。没有实现真实 AMEP、没有声称推理加速已经验收。
- **训练页**：读取后端已持久化数据集、显示样本数量和最多 8 张真实缩略图；训练配置仍是未保存的参数草稿与空监控图，不会开始训练；按钮明确禁用，以避免误导为实际可运行训练器。
- **数据集**：**已真正持久化**。创建数据集、一次选择最多 80 张图片和配对 `image.tags.txt`，以最多 3 个并发 HTTP 请求上传；后端验证图片并按 SHA-256 去重，提供分页缩略图、原图、修改/保存 Caption、删除。服务重启后仍可读取，训练页也能预览，但暂时未接入训练执行。

页面使用 Vue Router 哈希路由，Tauri / 静态托管无需服务器配置 history fallback。真实 API 由 `../api.ts` 调用，后端仍是 Python/FastAPI + Rust 调度。响应式 CSS 统一在 `../styles.css`。

验收：TypeScript `vue-tsc --noEmit` + Vite 构建、API contract 测试；真实浏览器界面需要后续在 Windows/Linux 及移动窗口检查。
