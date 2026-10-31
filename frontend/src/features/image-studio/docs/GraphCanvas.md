# GraphCanvas.tsx · React Flow 编辑器

对应源码：`../GraphCanvas.tsx`。使用 `@xyflow/react` 提供节点拖动、连线、选择、画布缩放；对上层回传节点位置、连接和删除操作。

**边界**：本组件只是编辑器，**不是推理引擎**。执行依赖由后端 `compile_workflow` 校验排序。参数模式不装载 React Flow 节点画布，通过 `React.lazy` 和 `Suspense` 减少初始化与渲染开销。

安全与性能：连接必须通过 `canConnect`，禁止环；画布节点应仅包含可序列化的元信息；避免在滑块每次变动时重新加载/创建完整工作流。底层节点位置更新与 Graph 结构变更分开处理。

**测试入口**：`npm run build`。浏览器交互（删除边、拖拽、快捷键、连接回调）需要后续 E2E 测试。
