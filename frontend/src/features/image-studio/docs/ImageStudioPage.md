# ImageStudioPage.tsx · 参数式创作工作台

对应源码：`../ImageStudioPage.tsx`。公开交互仅提供参数控制，不显示 Graph/React Flow。内部仍沿用唯一的 `StudioWorkflow`（`lumacarve.studio.workflow.v1`）数据模型和 JSON 任务 API，不创建第二套配置状态。

## 界面层级

- 顶部：图像工作室 / 生成、参考编辑、局部重绘模式（模型不支持时禁用）；参数预设导入、导出、恢复默认。
- 左侧：当前模型、可用图像输入/蒙版以及 LoRA Stack。参考图只在浏览器本地预览，模型能力尚未接入时不提交假的图像编辑任务。
- 中间：真实 PNG 输出画布、模型内最近 20 张输出缩略图；没有真实输出时使用静态空画布，而不展示可能误导用户的“示例生成图片”。下方是提示词、负面提示词和开始/取消生成。
- 右侧：Steps、Seed、画幅比例、Guidance 和高级参数；[RuntimeStatusPanel](runtime-status.md) 展示真实读取的后端配置与未采集状态；底部为简洁任务摘要。

导入的参数预设沿用原 Graph JSON 结构，服务端仍严格校验工作流。页面不再调用动态 `GraphCanvas`，因此不会加载 `@xyflow/react` 视图。

## 真正执行与非执行能力

Anima Base 1.0 的文字生成接入本地 FastAPI/SQLite 任务 API，点击生成返回排队、运行、成功/失败/取消状态；仅在任务真的返回 PNG 输出 ID 时显示结果。当前并无前端连接的编辑模型或 LoRA 训练引擎：切换其它模型只预览能力声明，不伪造 GPU 生图。

- 作业运行期间每 1.5 秒轮询该作业 ID，作业完成/页面卸载即停止；它不是 GPU 性能采集。
- 运行状态面板进入页面只读取一次，手动按「刷新」才再次读取。
- 参考图在浏览器创建受限预览对象 URL，卸载时释放；不在 JSON 中夹带图片二进制。
- 不渲染持续动画、重型玻璃滤镜或后台节点画布；模型相关计算均由 Python Worker 而非 React 执行。

## 验证

`cd frontend && npm run build && npm run test:runtime`。真实 GPU 端到端验证与移动端浏览器可视检查尚需在具备相应环境的机器上执行。
