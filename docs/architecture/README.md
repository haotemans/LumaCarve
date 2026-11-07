# LumaCarve 架构总览

项目目标：Windows 本地优先的图像生成、图像编辑与 LoRA 训练工作台；单 Python 虚拟环境、Graph 驱动执行、轻量参数 UI、按需模型加载、中国大陆与国际下载源。

> 本目录区分**已实现**与**目标架构**。切勿将目标目录、模型运行时、显存优化当成已有功能。最新平台发行与能力状态以 [发布状态清单](../release-status.md) 为准。

阅读顺序：

1. [01-repository-layout.md](01-repository-layout.md)：仓库文件夹划分、代码归属、迁移路径。
2. [02-tech-stack.md](02-tech-stack.md)：现有技术栈、后续组件选择、依赖原则。
3. [03-data-layout.md](03-data-layout.md)：模型、数据集、缓存、下载与任务输出的数据布局。
4. [ADR-0001-modular-monorepo.md](ADR-0001-modular-monorepo.md)：单仓库、单运行环境、独立模块的决策记录。
5. [ADR-0002-rust-scheduler-comfyui-reference.md](ADR-0002-rust-scheduler-comfyui-reference.md)：ComfyUI 架构参考，Rust 调度 / Python 模型计算的边界。
6. [ADR 0002：Tauri 2 Sidecar](adr/0002-tauri2-sidecar.md)：便携打包、安全边界与 GPU 运行时限制。

具体源文件的说明优先放在相应模块旁边，或沿用 `backend/docs/` 的已有说明。Vue 迁移决策见 [ADR 0001](adr/0001-vue3-frontend.md)。模块索引由根目录 `project-layout.toml` 记录，`tools/check_layout.py` 在 CI 中检查引用关系。

## 必须遵守的边界

- **Graph 是唯一流程定义**：参数模式只读取/更新 Graph 所暴露字段，不另建一套工作流。
- **Web UI 不操作 CUDA**：Vue 3 提供图形化参数工作台，内部 Graph 定义执行数据，PyTorch 工作进程负责实际推理/训练。
- **模型只加载一次**：同一任务的 LoRA Stack 复用基础模型；空闲时是否卸载由资源管理器决定。
- **一份代码配一份 Markdown**：新增源码模块必须补使用说明、输入输出、限制、相应测试；已有同领域服务和路由可共用领域文档，后续逐步补足细分说明。
- **不要混放文件**：下载中的模型不得被索引为“已安装”，模型权重/用户上传数据不得进入 Git。
- **不伪造状态**：没有 GPU 推理适配器时必须明确不可用，不能展示假生成结果。

## 当前状态

- 公开界面已迁移至 `frontend/src/vue/`，七个页面均为 Vue 3 单文件组件；`frontend/src/features/image-studio/` 只保留框架无关的工作流 JSON 与本地 API。旧 React 页面和 React Flow 已移除。
- 已有 `backend/lumacarve_server/`（HTTP API 与业务）和 `backend/lumacarve_runtime/`（执行策略）；后续按职责将业务再拆分到 services/storage/adapters。
- Rust `scheduler/` 已实现 DAG、签名、优先级队列与资源租约元数据策略，并提供可选 PyO3 绑定。当前只有 Graph 编译集成到 Python 的可选优选路径；执行队列仍由 Python 控制，**Rust 尚未接管实际 GPU 运行**。
- 当前 `LumaCarveData/model`、`assets`、`outputs`、`jobs.sqlite3` 仍按现有代码使用。**不会仅因为文档出现新目录就擅自迁移用户数据**。
