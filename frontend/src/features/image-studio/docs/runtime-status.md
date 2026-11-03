# Runtime Status · 前后端真实性约束

源码：`../runtime.ts`、`../../../vue/views/SystemView.vue`、`../../../vue/stores/studio.ts`。
测试：`frontend/scripts/runtime-contract.test.mjs`，并通过仓库根目录 `.github/workflows/frontend-ci.yml` 执行。

`GET /api/v1/runtime` 只返回 FastAPI 已知的环境配置与调度状态，不会为显示页面而初始化 CUDA、加载模型或运行 GPU Benchmark。

- `configured_engine` 是用户选择的后端；`engine=anima` 最多说明本地模型目录/依赖可访问，不等于 GPU 已装载权重。
- `gpu.measured=false`、`gpu.available=null` 表示未测量。Vue UI 显示“—”或“未知”，不绘制假的显存百分比。
- `inference_offload=auto|model_cpu|full` 是现有基本卸载配置，**AMEP 自适应显存规划尚未实现**。
- `optimization.anima.{adaln,rope,residual,ffn}` 为 `off|experimental`，只代表环境选项；尚未经过真实 GPU 数值、端到端性能和画质验收。
- 每次进入应用按需读取一次运行状态，用户主动刷新才发起新的 GET。图像任务每 1.5 秒轮询仅针对当前执行任务，而非 GPU 采样。

Vue 的 SystemView 显示真实状态；模型资源与生成任务分别由自己的 API 实际读取。不存在为了前端展示而启动后台的显存预测器。

验证：
```bash
cd frontend
npm run test:runtime
npm run build
```


`queue` 增加任务状态数量、队列容量和 Worker 状态，来自现有 SQLite 账本，不表示 GPU 探测。`GPU/VRAM` 若尚未实际测量继续显示未知（—）。
