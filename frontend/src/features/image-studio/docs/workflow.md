# workflow.ts · Graph 数据模型

对应源码：`../workflow.ts`。模型 `StudioWorkflow` 包含 `format/intent/nodes/edges`，当前序列化版本固定为 `lumacarve.studio.workflow.v1`。

**核心规则**：Graph 定义节点连接与流程；`exposed` 定义参数视图应显示的字段。增加 LoRA 是追加节点内部的 `loras[]`，不需要复制基础模型。工作流导入进行结构、字段及节点连接校验，但**不代表服务端接受该配置、模型已安装或 GPU 显存足够**。

`makeWorkflow` 建立默认模板；`validateImport` 仅用于浏览器导入校验；服务器端 `backend/lumacarve_server/workflows.py` 才是提交执行时的最终结构校验。新增 Graph 节点类型须同时更新服务端类型和双方测试。

**测试入口**：`frontend/npm run build` + `backend/tests/test_workflows.py`。不允许通过改目录重置或默默升级工作流 JSON 格式。


Anima Base 1.0 已作为默认初始模型（当前仅 `create`），Qwen 等仍保留在模型选择中但不宣称已接入后端。切换模式不会创建第二套 Graph 状态，后端实际执行能力仍以 API 为准。


首个可执行的 Anima 默认 Graph 模板直接暴露 `prompt`、`negativePrompt`、`steps`、`seed`、`aspect`、`guidance`；Anima 不支持透明背景，默认隐藏 `transparent`；原始内部 Graph JSON 中仍存在 `output` 节点，但 Vue 用户界面不提供节点编辑。任何暴露更改都写入同一个 Graph `exposed` 数组，不生成额外状态。

## 公开工作台不显示节点图

旧版 React GraphCanvas 源码已移除。公开 Vue 界面仅保留可编辑参数、预设 JSON 的导入导出与恢复默认。工作流仍是服务器唯一接受的 `lumacarve.studio.workflow.v1` 结构；仅更改展示方式，没有修改 JSON schema、任务执行顺序或 LoRA 数组语义。
