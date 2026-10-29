# 03 · Graph 工作流校验（workflows.py）

对应代码：\`lumacarve_server/workflows.py\` 与 \`routers/workflows.py\`；测试：\`tests/test_workflows.py\`。

契约：与 React 前端的 \`frontend/src/studio/workflow.ts\` 保持一致。JSON 版本 \`lumacarve.studio.workflow.v1\`；每个节点拥有 \`id/kind/params/exposed\`，连线只用于执行依赖，\`exposed\` 仅用于参数 UI。

请求 \`POST /api/v1/workflows/validate\`：
\`\`\`json
{"workflow":{"format":"lumacarve.studio.workflow.v1","intent":"create","nodes":[...],"edges":[...]}}
\`\`\`

校验包括：唯一 model / output、采样器、文本条件、节点类型和参数键、LoRA 权重、多图/蒙版节点与 intent 兼容、连接类型、环路、孤立节点以及输出可达性。返回规范化节点顺序和已启用的 LoRA 列表。

设计边界：校验通过 **不代表该模型已安装、支持指定编辑功能，或者显存足够**。本模块不触发 GPU、模型下载或图片生成。自定义插件节点不能绕过服务端类型注册。
