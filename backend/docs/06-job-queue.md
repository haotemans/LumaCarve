# 06 · 任务持久化与单 GPU 队列（jobs.py）

对应代码：\`lumacarve_server/jobs.py\`、\`routers/jobs.py\`；测试：\`tests/test_jobs.py\`。

SQLite 任务账本记录状态 \`queued/running/completed/failed/cancelled\`、工作流 JSON、输入资产 ID、执行结果/错误与创建更新时间。

HTTP API：
- \`POST /api/v1/jobs\`：校验 Graph 与必需图片/蒙版，然后进入队列；**未接入推理适配器时返回 503，绝不悄悄入队或伪造结果**。
- \`GET /api/v1/jobs\`、\`GET /api/v1/jobs/{id}\`：读取任务历史。
- \`POST /api/v1/jobs/{id}/cancel\`：队列中任务直接取消，运行中请求协作取消。

调度：单 worker 串行执行 GPU 图像任务；后续训练也必须与之共用 GPU 资源仲裁而不能单独抢显存。重启会把未完成的 \`running\` 标为 \`failed/server_restarted\`。\`queued\` 项留在持久化存储中；只有接入真正可用的模型适配器才会继续处理。任务日志不保存任何假图片。

取消：推理适配器需要定期检查 \`threading.Event\` 并在模型安全同步点停止，否则只是申请取消。该版本没有强行中断 CUDA 内核。

**目前状态：** 队列、数据库及 API 验证已完成；\`DisabledInference\` 为显式不可用适配器，没有安装/运行真正模型。
