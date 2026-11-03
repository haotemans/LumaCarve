# Image Studio Runtime Status · 双端真实状态边界

## 代码

- `../runtime.ts`：从本地 `/api/v1/runtime` 读取和严格解析只读配置快照。
- `../RuntimeStatusPanel.tsx`：在图像工作室右侧展示状态、基本显存策略、AMEP 未实现标记、四项实验内核配置。
- `../../../../scripts/runtime-contract.test.mjs`：使用 Vite SSR 加载实际 TypeScript 解析器；无需浏览器、Torch/CUDA 或真实后端。
- `../image-studio.css`：工作台局部样式，静态表面替代高成本模糊。

## 状态语义

`configured_engine=anima`：用户环境变量已选择 Anima；`engine=anima`：轻量的本地模型文件/依赖存在性检查通过。两者均**不是 GPU 已经启动/显卡可用的证明**。

`gpu.measured=false` / `gpu.available=null`：本地 API 未进行 GPU 探测，前端显示「未采集」，不将未探测误报为无 GPU；显存占用固定展示 `—`，绝不构造 0% 或模拟用量。

`inference_offload=auto|model_cpu|full`：仅表示基础 Diffusers 组件驻留选择。**不是** LumaCarve 后续规划的 AMEP 智能预测/自适应资源调度器，界面应明确显示「智能自动均衡：尚未接入」。

`optimization.anima.{adaln,rope,residual,ffn}` 的 `experimental` 仅表示后端环境配置。界面标签必须使用「实验配置」，不将其称为已启用、已验证或已实际加速的 Kernel。老版本后端不提供这些字段时必须显示「未知」，不能假定 off。

## 刷新及性能

- 工作台进入时发起**一次**只读 GET；使用 AbortController 在卸载时取消。
- 用户按下「刷新」才发起下一次请求。不会定时轮询 GPU/VRAM；正常的生成任务状态轮询仍独立保留，且只在有活动任务时运行。
- API 收集 Settings/已有队列元数据，不导入 CUDA、Triton/PyTorch 或执行任何 GPU Benchmark。
- 它不是动态可修改的性能设置页：要更改 Python Worker 推理设置，当前需修改环境变量并重新启动后端。尚未接入的 AMEP 不显示虚假操作按钮。

## 验证命令

```shell
cd frontend
npm install --no-audit --no-fund
npm run test:runtime
npm run build
```

`backend/tests/test_server.py` 同步验证状态字段的真实性；GitHub Actions 的 frontend/backend CI 分别执行 Node 和 Python 检查。

## 用户界面决策

公开的图像工作室采用参数模式（模型、提示词、LoRA、Steps、Guidance、Seed、画幅、预览及结果）。`StudioWorkflow` 和服务端 Graph JSON **保留为内部序列化与执行结构**，不再公开 React Flow 节点编辑器。

旧的 `GraphCanvas.tsx` 仍在仓库以便未来迁移/内部调试，但主页面不会导入它；默认参数界面不加载 React Flow Bundle。旧工作流 JSON 仍可以作为参数预设导入/导出，但不允许声称后端执行能力超出当前 Anima T2I 接口。
