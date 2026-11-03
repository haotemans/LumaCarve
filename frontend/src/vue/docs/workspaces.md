# Vue 3 其它图形化工作台

**对应源码**：`../views/TrainingView.vue`、`GalleryView.vue`、`ModelsView.vue`、`DatasetsView.vue`、`TasksView.vue`、`SystemView.vue`。

- **作品画廊**：读取 SQLite 真实作业列表，对 `completed` 任务严格验证输出 ID 后显示 PNG 缩略图；无文件时只显示空状态，不使用虚构示例。
- **模型管理**：只读已索引的本地模型文件与下载目录；下载按钮触发真实 `POST /api/v1/downloads`，仅下载被后端允许的可信条目；只有用户启动下载后才轮询相应下载任务，不构造虚假的进度条。
- **任务队列**：只读真实 `GET /api/v1/jobs`；手动刷新、取消队列/运行中的任务；不假设能强制终止正在执行的 CUDA Kernel。
- **运行环境**：只读配置、未知的 GPU VRAM、基础 offload 策略和实验内核配置。没有实现真实 AMEP、没有声称推理加速已经验收。
- **训练页**：提供静态可编辑的训练参数草稿与空监控图，不会开始训练；按钮明确禁用，以避免误导为实际可运行训练器。
- **数据集**：浏览器会话内选取最多 80 张图片、配对 `image.tags.txt`、编辑并导出 Caption；URL 在移除/卸载时释放，数据不在后端持久化，不对训练器产生作用。

页面使用 Vue Router 哈希路由，Tauri / 静态托管无需服务器配置 history fallback。真实 API 由 `../api.ts` 调用，后端仍是 Python/FastAPI + Rust 调度。响应式 CSS 统一在 `../styles.css`。

验收：TypeScript `vue-tsc --noEmit` + Vite 构建、API contract 测试；真实浏览器界面需要后续在 Windows/Linux 及移动窗口检查。
