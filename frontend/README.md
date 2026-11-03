# LumaCarve WebUI

React + TypeScript + Vite，供 **WebUI 与 Windows/Linux Tauri 2 桌面端共用**。图像工作室源码与逐模块文档集中在 [`src/features/image-studio/`](src/features/image-studio/README.md)。

## 本地开发

需要 Node.js 22 或受 Vite 支持的版本。

```bash
cd frontend
npm install
npm run dev
npm run test:runtime
npm run build
```

开发页面：<http://localhost:5173>。通过 `VITE_LUMACARVE_API_URL` 可选择本地 API（默认 `http://127.0.0.1:8000`）。

## 参数式 Image Studio

公开界面是**简单的图像创作工作台**，不再出现 Graph/React Flow 编辑入口。左右侧提供模型、LoRA、采样参数、真实运行状态；中间显示实际输出 PNG、提示词及取消控制。无输出时显示静态空画布，不用演示插画冒充生成结果。

`StudioWorkflow` 仍是统一的、可序列化、受后端校验的 JSON 结构；按钮修改直接写回相同数据模型。用户可导入/导出参数预设，但不需要管理节点与连接线。保留 `GraphCanvas.tsx` 的原始源文件，主页面不再导入其渲染逻辑。

**Anima Base 1.0** 是当前唯一接入的真实文字生成执行适配器，提交本地 `/api/v1/jobs`，成功后从 `/api/v1/outputs/{id}` 显示 PNG。真实生成取决于用户已安装模型、PyTorch 和 CUDA；尚未实机验证。参考编辑、局部重绘、其它模型的前端能力信息仍属预设，不能当作已接入的推理功能。训练及部分资源管理页面仍是原型。

## 运行状态与性能约束

右侧 [RuntimeStatusPanel](src/features/image-studio/docs/runtime-status.md) 只读 `GET /api/v1/runtime`：

- 进入图像工作室时读取一次，主动点击「刷新」时再次读取，不对 GPU 进行后台监控。
- GPU 未探测时显示「未采集」，显存使用量显示 `—`；不假设有无显卡。
- `auto` 仅为基础 CPU Offload 配置，**AMEP 智能自动均衡尚未实现**。
- Triton AdaLN/RoPE/Residual/FFN 的 `experimental` 表示后端配置，不表示已实测加速。
- 不在 UI 加载 GPU 预测模型或自动进行 Triton Autotune；隐藏大面积模糊环境光，减少页面渲染负担。

## 其它页面与限制

现有出图管理、数据集管理、训练页面、模型管理、设置与插件页面仍有部分演示数据和未接通后端的功能。它们必须明确标识状态；不能把示意素材当作生成结果。

功能在无 GPU 的 CI 中验证 TypeScript/前端构建、运行状态纯解析器测试、Python/FastAPI 状态 API 单元测试。移动端视觉效果及真实 CUDA 性能需要具备对应硬件的环境另行验证。

技术说明：[项目架构](../docs/architecture/README.md) · [后端 Anima 适配](../backend/docs/17-anima-adapter.md)。
