# Image Studio · 图像工作室

**源代码按功能集中**，避免视图、Graph 和样式散落在不同目录。迁移仅修改源码位置和导入路径，保留原有对外工作流格式、参数与 UI 行为。

| 代码 | 同步 Markdown | 核心职责 |
|---|---|---|
| `ImageStudioPage.tsx` | [docs/ImageStudioPage.md](docs/ImageStudioPage.md) | 图像创作/编辑、参考图、蒙版、LoRA、参数视图 |
| `workflow.ts` | [docs/workflow.md](docs/workflow.md) | 统一 Graph 数据与参数暴露结构 |
| `GraphCanvas.tsx` | [docs/GraphCanvas.md](docs/GraphCanvas.md) | React Flow 节点编辑，仅 Graph 模式按需加载 |
| `image-studio.css` | [docs/image-studio-css.md](docs/image-studio-css.md) | 轻量 UI 样式、断点和可访问性 |

依赖方向：`ImageStudioPage` → `workflow`；图编辑器 `GraphCanvas` → `workflow`。Graph 编辑器以 `React.lazy` 在需要时引入，参数模式不额外创建第二套状态。Graph/参数模式都不直接调用 GPU。

验证：`cd frontend && npm run build`（TypeScript 类型检查 + Vite 打包）。

当前生图、编辑、训练均尚未接入真实 PyTorch 执行引擎。UI 示例预览不能当作生成结果。
