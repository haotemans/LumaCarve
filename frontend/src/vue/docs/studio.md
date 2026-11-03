# Vue 3 Image Studio

代码：`../views/StudioView.vue`、`../stores/studio.ts`。

**可视交互**：左侧模型、Prompt、0–N LoRA，参考图选择和仅本地可导出的局部涂抹蒙版；中间真实生成画布和缩略图；右侧 Steps、Guidance、Seed、画幅及只读配置状态。默认 Anima Base 1.0，参数式操作，不展示节点流；编辑/重绘模型尚未接入会明确提示。

**唯一数据源**：Vue/Pinia 的 `workflow` 持有与旧前端完全一致的 `lumacarve.studio.workflow.v1` JSON。复用 `src/features/image-studio/workflow.ts` 的 `makeWorkflow`/`updateNodeValue`/`validateImport`，不改变后台 Graph 参数协议。切换模型重建对应模板并尽可能保留提示词，避免将 Anima 参数强塞进不兼容的编辑工作流。

**真实执行**：复用 `src/features/image-studio/api.ts` 的 `POST /api/v1/jobs` / 状态查询 / 取消 / PNG `output_id` 验证。只在有运行任务时按 1500ms 轮询；页面卸载停止 timer，后端队列继续执行；返回页面可通过 `GET /api/v1/jobs` 恢复已完成结果。

**无伪造**：无真实 PNG 输出时使用明确的抽象空画布（仅 UI 装饰），不加载假作品。没有 CUDA 测量时不显示 VRAM 百分比。Triton 内核的 `experimental` 仅表示配置而非验证。

**性能**：全部 CSS 静态，零 React/React Flow 运行时，不持续在前端进行 GPU 预测、实时采样或后台渲染；缩略图图片通过 `loading="lazy"` 延迟加载。

验证：`cd frontend && npm run test && npm run build`。实际生成需 Anima 模型权重、CUDA、后端进程。
