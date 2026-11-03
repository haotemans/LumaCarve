# LumaCarve · Vue 3 图形化工作台

LumaCarve WebUI 与未来的 Windows/Linux Tauri 2 共用一个前端：**Vue 3 Composition API + TypeScript + Vite + Pinia + Vue Router**。不再依赖 React/React Flow。

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
| LoRA 训练 | 参数表单与空的监控画布。**训练执行后端尚未接通**，启动按钮禁用 |
| 作品画廊 | 从后端已完成任务读取真实 PNG，查看/筛选，不再展示演示图片 |
| 模型管理 | 读取本地权重索引和下载目录；用户明确操作后可启动受控下载 |
| 数据集 | 只在浏览器会话中导入图片及配对 Caption（含 `image.tags.txt`），可导出当前 Caption，尚未连接持久化后端 |
| 任务队列 | 读取 SQLite 的真实任务状态，支持手动刷新与请求取消 |
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
