# LumaCarve WebUI

图像工作室已经迁入 [`src/features/image-studio/`](src/features/image-studio/README.md)：代码、Graph、独立样式与逐文件 Markdown 集中在一起。旧版训练/资源页面仍在 `src/pages/`，后续逐个迁移，不一次性破坏现有构建。全局结构与技术选择见 [架构规范](../docs/architecture/README.md)。

React + TypeScript + Vite 前端初版，供 **WebUI 与未来的 Tauri 2 / Rust 桌面壳共用**。

## 启动

需要 Node.js 20.19+ 或 22+。

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 。

生产构建：`npm run build`，预览：`npm run preview`。

## 当前已实现（前端）

- 浅色毛玻璃响应式工作台，顶部双层导航与资源检索。
- **出图管理**：瀑布式网格、收藏、搜索、筛选、批量选择、本地图片导入、参数详情与复制。
- **训练采样**：按任务集合归档；Epoch 时间轴、采样预览与任务对比。
- **数据集管理**：独立页面、图片 / Caption 对照、选择数据集、本地图片与同名 `.txt` 导入、前端编辑 Caption。
- 训练三栏、图像工作室（文字生成 / 多参考图编辑 / 局部重绘）、模型管理、插件管理、任务历史与设置的可视化 UI。
- **图像工作室**：根据 Graph 节点暴露字段显示参数控件；可添加任意数量 LoRA、选择参考图（Qwen-Image-2.1 最多 10 张）、在原图上绘制并导出透明 PNG 蒙版、导入/导出工作流 JSON。
- **Graph 视图**：按需动态加载 React Flow，支持添加、移动、删除、连接节点及暴露参数。与参数视图共用一份工作流定义。
- 参考图只保留在当前浏览器会话；预览缩放到最大边 1600 像素，切换页面可释放对象 URL。工作流 JSON 不嵌入图片原始二进制内容。

## 范围说明

这里是**可运行的前端原型**，包含明确标记的示例数据。训练、采样、真实生成与编辑、GPU 监控、模型自动扫描、PNG 内嵌生成元数据写入、磁盘持久化、插件安装等**尚未接入 Python/FastAPI 后端**；按钮不会冒充完成真实训练/生图。浏览器中导入的本地图片与编辑状态在当前会话中可用，刷新页面后不保证保存。后续先接入 REST 与任务进度（优先考虑 SSE），仅在确有双向实时数据需求时再使用 WebSocket。

未引入外部人物图像，卡片默认使用本地 SVG 绘制的原创占位插画。

## 图像工作室设计约定

- **统一图像工作室**：取代仅有文字生图的名称；包含生成、参考图编辑、局部重绘。
- **Graph 定义流程**：React Flow 管理流程节点和连接；参数模式根据节点的 `exposed` 字段决定显示控件，不需要渲染 Graph 画布。
- **能力驱动**：参考图数量、蒙版和 RGBA 选项由模型适配器能力声明决定。当前模型能力表只用于前端布局验证，不代表本项目已能运行推理。
- **LoRA Stack**：每个节点拥有任意长度列表；实际的兼容性和显存预算由 Python 模型运行时检查。
- **性能**：Graph 模式按需加载 `@xyflow/react`；参考图使用缩略图，避免渲染多个全尺寸纹理。

[Qwen-Image-2.1 原始模型文档](https://huggingface.co/Qwen/Qwen-Image-2.1) · [React Flow 官方文档](https://reactflow.dev/)
