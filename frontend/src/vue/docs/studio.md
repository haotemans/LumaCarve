# Vue 3 Image Studio

代码：`../views/StudioView.vue`、`../stores/studio.ts`。

**可视交互**：左侧模型、Prompt、0–N LoRA，参考图选择和仅本地可导出的局部涂抹蒙版；中间真实生成画布和缩略图；右侧 Steps、Guidance、Seed、画幅及只读配置状态。默认 Anima Base 1.0，参数式操作，不展示节点流；编辑/重绘模型尚未接入会明确提示。

**唯一数据源**：Vue/Pinia 的 `workflow` 持有与旧前端完全一致的 `lumacarve.studio.workflow.v1` JSON。复用 `src/features/image-studio/workflow.ts` 的 `makeWorkflow`/`updateNodeValue`/`validateImport`，不改变后台 Graph 参数协议。切换模型重建对应模板并尽可能保留提示词，避免将 Anima 参数强塞进不兼容的编辑工作流。

**真实执行**：复用 `src/features/image-studio/api.ts` 的 `POST /api/v1/jobs` / 状态查询 / 取消 / PNG `output_id` 验证。只在有运行任务时按 1500ms 轮询；页面卸载停止 timer，后端队列继续执行；返回页面可通过 `GET /api/v1/jobs` 恢复已完成结果。

**无伪造**：无真实 PNG 输出时使用明确的抽象空画布（仅 UI 装饰），不加载假作品。没有 CUDA 测量时不显示 VRAM 百分比。Triton 内核的 `experimental` 仅表示配置而非验证。

**性能**：全部 CSS 静态，零 React/React Flow 运行时，不持续在前端进行 GPU 预测、实时采样或后台渲染；缩略图图片通过 `loading="lazy"` 延迟加载。

验证：`cd frontend && npm run test && npm run build`。实际生成需 Anima 模型权重、CUDA、后端进程。

## 本轮模型文件一致性修复

早期浏览器的 `webkitdirectory` 仅提供本地文件名，不能让后端 Worker 读取这些文件；前端现在优先使用服务端索引返回的 `anima_snapshot` 来选择真正完整的 Diffusers ModularPipeline 目录。`backendReady` 只表示轻量依赖/文件准备完毕，不等于 CUDA 通过。未安装或选中不一致路径时禁用真实生成按钮；API 端双层检查不匹配的 checkpoint，不能悄悄用另一套权重生成。

## 精简交互（2026-11-07）

- 基础模型选择与提示词保持直接可见；完整路径藏于可展开的「模型路径」，不再用装饰头像占据操作区。
- LoRA 是可折叠的真实编辑区域：标题始终显示条目数与启用数，添加按钮保持可见且会自动展开；折叠**只影响显示**，绝不卸载或清空 Graph 的 LoRA 数组。
- Steps 与画幅维持常显，CFG/Seed 折叠在「高级参数」内，并在折叠标题展示当前值；更改直接写入原有 Graph JSON，不新增第二套参数。
- 右侧状态仅展示 API 在线情况和**已采集**的 GPU 可用性；未检测、未启用、未测量分开。CPU offload 与 Triton 配置移入「运行详情」，实验配置不显示为性能提升。
- 空画布仅显示真实空状态和下一步；生成按钮按后端准备状态继续禁用，禁止假图片、虚构 GPU 利用率。
- 预设菜单收起到「工具」下，导入/导出 JSON、重置动作保持可用。窄屏仍保留模型、提示词、生成按钮及状态，触屏按钮具备可访问名称。

验证：frontend 单元测试、vue-tsc/Vite；响应式与键盘交互仍需在目标桌面实际视觉检查。
