# 02 · HTTP 服务与健康检查（app.py）

对应代码：\`lumacarve_server/app.py\`。对应测试：\`tests/test_server.py\`。

技术栈：FastAPI / Uvicorn；Python 3.11+。通过 \`create_app(settings)\` 注入配置，方便无 GPU 单元测试。重型模型依赖不在 HTTP 进程导入时加载。

运行：
\`\`\`powershell
cd backend
py -m pip install -e ".[dev]"
py -m uvicorn lumacarve_server.app:app --host 127.0.0.1 --port 8000
\`\`\`
打开 \`http://127.0.0.1:8000/docs\` 访问自动生成的 OpenAPI 文档。

接口：
- \`GET /api/v1/health\`：API 存活，不等同于模型可用。
- \`GET /api/v1/runtime\`：目前报告 \`not_connected\`，不会虚构 GPU 显存。

请求由 Host 白名单和 Origin 白名单限制。CORS + Origin 检查仅是本地演示的基本安全控制，并非互联网部署的身份鉴权。

**状态：** API 基础启动已实现；模型列表、上传、工作流和生成任务在后续按模块增量接入。


`GET /api/v1/runtime` 另提供 `queue_scheduler`（实际 Rust/Python 调度后端）和 `queue_scheduler_error`（后台队列故障；正常为 null）。这个状态读取 **当前 FastAPI 实例** 的队列，而不是模块级全局应用，以保证测试和多个隔离实例的数据正确。
