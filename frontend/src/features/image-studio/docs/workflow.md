# workflow.ts · Graph 数据模型

对应源码：`../workflow.ts`。模型 `StudioWorkflow` 包含 `format/intent/nodes/edges`，当前序列化版本固定为 `lumacarve.studio.workflow.v1`。

**核心规则**：Graph 定义节点连接与流程；`exposed` 定义参数视图应显示的字段。增加 LoRA 是追加节点内部的 `loras[]`，不需要复制基础模型。工作流导入进行结构、字段及节点连接校验，但**不代表服务端接受该配置、模型已安装或 GPU 显存足够**。

`makeWorkflow` 建立默认模板；`validateImport` 仅用于浏览器导入校验；服务器端 `backend/lumacarve_server/workflows.py` 才是提交执行时的最终结构校验。新增 Graph 节点类型须同时更新服务端类型和双方测试。

**测试入口**：`frontend/npm run build` + `backend/tests/test_workflows.py`。不允许通过改目录重置或默默升级工作流 JSON 格式。
