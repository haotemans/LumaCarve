# 04 · 模型索引（models.py）

对应代码：\`lumacarve_server/models.py\`、\`routers/models.py\`；对应测试 \`tests/test_models.py\`。

\`GET /api/v1/models\` 列举 \`LumaCarveData/model/{dit,te,vae,lora,checkpoints}\` 内的 \`.safetensors\` 文件，包括类别、相对路径、字节数。

- **只读索引**：不会加载权重、自动下载、访问网络或执行第三方 Python 文件。
- **防路径逃逸**：符号链接指向模型根目录外时跳过；实际推理读取仍需再次检查安全性。
- **前端模型名称是预设模型家族，不等于已在磁盘上存在完整权重。**
- \`backend_ready=false\` 说明目前尚未接入可执行的具体模型适配器。

后续将把模型家族适配器、文件清单与哈希校验独立实现；不能用仅发现文件的结果来声明模型可运行。
