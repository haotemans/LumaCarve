# ADR 0001: Vue 3 作为 LumaCarve 单一前端

状态：接受（2026-11-03）

## 背景

已有 React / React Flow 原型，公开界面转向参数优先。用户决定使用 Vue 3 并希望减少文字说明、重视直观的图形化桌面体验。底层 Rust Core 和 Python Worker 与 UI 框架无关。

## 决定

采用 **Vue 3 Composition API + TypeScript + Vite + Pinia + Vue Router (Hash History)**，共享 WebUI 与未来 Windows/Linux Tauri 2 容器。迁移所有公共工作台界面，不在一个产品中长期并行运行 React 和 Vue。

维持 `lumacarve.studio.workflow.v1` 作为内部生成任务序列化格式，无需要求用户编辑 Graph/React Flow。复用框架无关的工作流校验和 API 模块。

## 非目标

此次迁移不实现新的训练 Worker、Qwen 图像编辑、AMEP 智能调度或实际 CUDA GPU 遥测；不允许靠虚假前端结果演示这些能力。

## 代价与风险

现有 React 页面必须重写为 Vue 单文件组件；旧的 React 插件或状态无法无损复用。独立 PR 避免混入 Anima Triton Kernel 开发。前端依赖彻底移除 React 和 React Flow，CI 必须运行 `vue-tsc` 与 Vite 构建。

## 验证

Vue Router 各页面可导航，状态未知明确显示；Anima 任务 API 可接通，空画布不冒充生成成功；低功耗 UI 不持续创建 GPU 大面积模糊动画；GitHub CI 的 frontend、backend 和项目结构校验通过。
