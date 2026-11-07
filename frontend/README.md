# LumaCarve · Vue 3 图形化工作台

LumaCarve WebUI 与已集成的 Windows/Linux Tauri 2 桌面端共用一个前端：**Vue 3 Composition API + TypeScript + Vite + Pinia + Vue Router**。不再依赖 React/React Flow。

## 启动

```bash
cd frontend
npm install --no-audit --no-fund
npm run dev
npm run test
npm run build
```

在浏览器打开 `http://localhost:5173/#/studio`。本地后端默认 `http://127.0.0.1:8000`，可通过 `VITE_LUMACARVE_API_URL` 覆写。

## 图形化界面

| 页面 | 当前功能 |
|---|---|
| 图像生成 | Anima Prompt、负面提示词、LoRA、画幅、Steps、CFG、Seed、真实生成结果与取消任务 |
| LoRA 训练 | 可选择已保存训练集并预览真实图片；参数草稿与空监控画布。**训练 Worker 尚未接通**，启动按钮禁用 |
| 作品画廊 | 从后端已完成任务读取真实 PNG，查看/筛选，不再展示演示图片 |
| 模型管理 | 本地权重与有效 Anima ModularPipeline 快照分离显示；可使用明确下载动作启动受控下载 |
| 数据集 | **已接入真实后端**：创建训练集、批量图片/Caption 导入、分页缩略图、编辑并保存 `image.tags.txt`、删除、重启后继续使用 |
| 任务队列 | 读取 SQLite 的真实任务状态，按状态筛选、分页、统计、取消 |
| 运行环境 | 只读 API 状态、CPU 卸载配置及 Anima Triton 选项，不伪造 GPU/VRAM 数字 |

数据执行结构继续使用原有 `lumacarve.studio.workflow.v1` JSON。UI 为简洁参数式；内部保留 Graph 作为序列化结构，**不展示节点编辑器**。

## 代码与文档

- `src/main.ts`、`src/vue/App.vue`、`src/vue/router.ts`：应用入口和导航。
- `src/vue/views/`：七个 Vue 单文件组件页面。
- `src/vue/stores/studio.ts`：Pinia 的工作流/任务统一状态。
- `src/vue/api.ts`：只读索引、下载与任务接口。
- `src/features/image-studio/{workflow,api,runtime}.ts`：复用框架无关的 TypeScript 协议与校验。
- 源码职责与测试说明：[Vue Studio](src/vue/docs/studio.md)、[其它工作台](src/vue/docs/workspaces.md)、[API 边界](src/vue/docs/api.md)。
- 架构决策：[ADR 0001](../docs/architecture/adr/0001-vue3-frontend.md)。

**后端真实能力限制**：当前已接线的是 Anima Base 1.0 文字生成任务，不保证目标 GPU 的实际驱动/模型权重就绪。Qwen 编辑、训练 Worker、AMEP 智能自动均衡、真实 GPU 遥测尚未完整实现。

**验证**：GitHub CI 执行 `vue-tsc --noEmit`、Vite 构建和运行状态测试。界面视觉及 GPU 性能需要在实际设备上检查。

## 本轮前后端同步完善

- 真实数据集接口：`GET/POST /api/v1/datasets`、单图上传、缩略图、Caption 保存、删除；文件写入同一个 `LumaCarveData/datasets/`，不是刷新即消失的浏览器预览。
- 任务接口：`GET /api/v1/jobs?state=completed&limit=30&offset=0` 提供 `total`、`counts`；任务页面按状态展示和分页，不运行额外的 GPU 性能预测。
- 模型识别：`GET /api/v1/models` 增加 `anima_snapshot`，与普通单文件 `.safetensors` 区分；前端不会把仅通过浏览器读取的文件夹误报为 GPU 已安装模型。
- Vue / FastAPI 共用同一数据结构，未修改 Rust 图编译与 Triton Kernel；GPU 真实出图、训练执行及 VRAM 遥测仍需后续实机实现。

详见 [数据集后端设计](../backend/docs/24-dataset-library.md) 和 [Vue 工作区说明](src/vue/docs/workspaces.md)。

Windows 可使用仓库根目录的 `.\tools\start-dev.ps1` 一起启动 Vue 与 FastAPI，避免 `npm.ps1` 的 ExecutionPolicy 问题；Linux 对应 `./tools/start-dev.sh`。默认共用 `LumaCarveData`。详见 [启动说明](../docs/architecture/04-local-dev-launch.md)。

## 桌面便携版

Windows 仅发布无需安装的 ZIP（解压运行 `LumaCarve.exe`），Linux 仅发布 AppImage；不再发布 NSIS / DEB 安装包。Windows ZIP 必须保留内置 API 副程序和 `portable.flag`。解压目录旁建立 `LumaCarveData/` 保存用户数据。详见 [构建和发布规范](../docs/ci-build.md)。

**当前发行状态：** Windows 便携预览版 v0.2.3；Linux AppImage v0.2.2。便携包仅包含轻量本地 API，不包括 GPU Worker、Anima 权重或 LoRA 训练。请参阅 [发行与功能状态](../docs/release-status.md)。

## 图形化表达与界面层级（2026-11-07）

生成页以模型、Prompt、画布、Steps、画幅和执行按钮为主；LoRA、CFG/Seed、路径、实验内核按需展开。训练页仅保留可编辑草稿与真实空监控，不绘制虚构 Loss/GPU 曲线。状态以短文字和可辨识的视觉符号传达；不为装饰增加图形、文字或 GPU 开销。细节见 [Studio](src/vue/docs/studio.md) 与 [工作区](src/vue/docs/workspaces.md)。
