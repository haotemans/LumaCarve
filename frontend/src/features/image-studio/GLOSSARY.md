# Image Studio 术语表

本术语表只描述 LumaCarve 中用户和工程文档所说的概念；具体类型、接口和限制以对应代码与测试为准。

| 术语 | 定义 | 不等于 |
|---|---|---|
| 图像工作室（Image Studio） | 用户通过提示词、模型、LoRA、画幅等参数创建或编辑图像的统一工作区。 | 只有文生图或仅用于演示的静态页面。 |
| 参数工作台（Parameter Workspace） | 公开的表单式界面，修改后直接更新同一个内部工作流对象。 | 另一套与执行图独立的配置；可视化节点编辑器。 |
| 内部工作流（StudioWorkflow） | 前后端约定的 `lumacarve.studio.workflow.v1` JSON 数据结构，序列化节点/连接与参数，后端验证后执行。 | 对用户公开的 React Flow 工作台。 |
| 预设（Preset） | 可导入或导出的内部工作流 JSON，用于恢复模型、提示词、参数与 LoRA 配置。 | 包含参考图二进制、保证可在当前模型上执行的任务文件。 |
| 推理后端配置（Configured Engine） | 由本地环境变量选择的模型适配器，如 Anima。 | GPU 上已经加载并运行的模型。 |
| 本地资源就绪（Local Resources Ready） | 轻量检查完整模型目录与所需依赖存在。 | CUDA 已通过、GPU 已验证或可保证生成成功。 |
| GPU 遥测（GPU Telemetry） | 由实际 GPU Worker 在运行期测量并报告的设备状态、显存用量与耗时。当前 UI 的 `—` 表示未采集。 | `gpu.available=false` 的假定、预测数据或运行配置。 |
| 基础自动 CPU 卸载（Auto CPU Offload） | Diffusers 按基本策略在 GPU 与 CPU 间调度模型组件的当前执行模式。 | 智能预测和自适应驻留规划器 AMEP。 |
| AMEP（自适应显存与执行规划器） | 规划中的执行预算和资源驻留决策系统，强调离线画像、任务边界决策与几乎零 GPU 预测开销；当前尚未接入。 | 已经上线的自动均衡功能。 |
| Triton 实验配置 | 用户在环境变量中指定某个 Anima 融合 Kernel 的 `experimental` 模式。 | 已加载、已编译、正在运行或经过性能验收。 |
| 真实生成结果（Generated Output） | 本地作业完成后返回有效输出 ID 并经后端 URL 加载的实际 PNG。 | UI 示例插画、占位图或未成功任务的预览。 |

数据定义与真实性边界：[`docs/runtime-status.md`](docs/runtime-status.md)、[`docs/workflow.md`](docs/workflow.md)。
