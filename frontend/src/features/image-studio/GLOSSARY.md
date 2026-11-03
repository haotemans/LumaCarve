# Image Studio 术语

| 术语 | 定义 |
|---|---|
| 图像工作室 | 参数优先的图像生成/编辑工作区，前端使用 Vue 3。 |
| StudioWorkflow | 后端认可的 `lumacarve.studio.workflow.v1` 内部 Graph JSON，用户无需编辑节点。 |
| 参数预设 | 可导入/导出的工作流 JSON，不包含原始图片二进制。 |
| 本地模型就绪 | 轻量的文件和依赖检查，不等于实际 CUDA 生成成功。 |
| GPU 遥测 | 实际硬件上的显存/耗时观测；当前未采集不得虚构数据。 |
| CPU Offload | 已有的基础显存卸载模式，不等于规划中的 AMEP。 |
| AMEP | 尚未实现的自适应显存与执行规划器，要求不在生成过程中消耗 GPU 运行预测。 |
| Triton 实验配置 | 环境变量中的 `experimental`，不代表内核已经加载或确认更快。 |
| 真实生成结果 | SQLite 任务完成后，经输出 ID 验证并由 FastAPI 返回的 PNG 文件。 |
| 数据集本地预览 | 浏览器会话中的图片/Caption 编辑，不等于已保存训练数据集。 |

相关代码：[Vue 工作台](../../vue/docs/studio.md)、[工作流](docs/workflow.md)。
